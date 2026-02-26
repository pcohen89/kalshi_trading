# Architecture — Kalshi Trading System (V1)

Agent-readable codebase map. For conventions and workflow rules, see `CLAUDE.md`.

## Module Dependency Graph

```
main.py ──> cli_interface.py ──> trade_executor.py ──> kalshi_client.py ──> config.py
      │                                                      ^                   ^
      ├──> portfolio_tracker.py ───────────────────────────┘                   │
      ├──> trade_logger.py (standalone, imports config for log level) ─────────┘
      └──> kalshi_client.py (shared instance passed to executor + tracker)
```

## Data Flow

```
User input ─> MainApp (main.py)
                ├── portfolio view ─> PortfolioTracker ─> KalshiClient ─> Kalshi REST API
                ├── place a trade  ─> TradingCLI sub-loop
                │                        ├── search/trade ─> TradeExecutor ─> KalshiClient ─> Kalshi REST API
                ├── open orders    ─> TradeExecutor ─> KalshiClient ─> Kalshi REST API
                ├── cancel order   ─> TradeExecutor ─> KalshiClient ─> Kalshi REST API
                └── trade history  ─> TradeLogger ─> logs/trades.jsonl

Trade events ─> TradeLogger ─> logs/trades.log + logs/trades.jsonl + logs/errors.log
```

## Module Inventory

| File | Lines | Purpose |
|------|-------|---------|
| `main.py` | 130 | Top-level entry point; initialises shared dependencies, routes menu to all modules |
| `config.py` | 127 | Loads `.env`, validates credentials, exposes environment-aware config |
| `kalshi_client.py` | 604 | Authenticated HTTP client for Kalshi API v2 with RSA signing, retries, rate-limit handling |
| `trade_executor.py` | 339 | High-level trade operations with input validation; wraps KalshiClient |
| `portfolio_tracker.py` | 634 | Position listing, unrealized P&L (mark-to-market), realized P&L (settlements + FIFO fill matching) |
| `trade_logger.py` | 373 | Event logging to rotating `.log` files + `.jsonl` structured store; CSV export |
| `cli_interface.py` | 447 | Interactive menu-driven CLI for trading operations (launched as sub-loop from main.py) |

## Exceptions

All custom exceptions and where they originate:

| Exception | Module | Raised when |
|-----------|--------|-------------|
| `ConfigurationError` | `config.py` | Missing/invalid env vars (API key, environment, log level) |
| `KalshiAPIError` | `kalshi_client.py` | HTTP errors, auth failures, max retries exceeded, invalid key file |
| `TradeExecutionError` | `trade_executor.py` | Validation failures (side, qty, price) or KalshiAPIError during trade ops |
| `PortfolioError` | `portfolio_tracker.py` | Failed position/settlement/fill fetches or market price lookups |
| `TradeLoggerError` | `trade_logger.py` | Naive datetime passed to date-range filter |

## Module Details

### config.py

Loads `.env` at import time via `python-dotenv`. No class — just module-level functions.

| Function | Signature | Returns |
|----------|-----------|---------|
| `get_config` | `() -> dict` | Full config dict: `api_key`, `api_secret`, `environment`, `log_level`, `api_base_url` |
| `get_api_credentials` | `() -> tuple[str, str]` | `(api_key, api_secret)` |
| `get_api_base_url` | `() -> str` | Base URL for current environment |
| `get_environment` | `() -> str` | `"sandbox"` or `"production"` |
| `get_log_level` | `() -> str` | Log level string (e.g. `"INFO"`) |
| `is_production` | `() -> bool` | Whether environment is production |
| `validate_config` | `() -> bool` | Validates config; raises `ConfigurationError` on failure |

Environment variables: `KALSHI_API_KEY`, `KALSHI_API_SECRET` (path to `.pem` file), `KALSHI_ENVIRONMENT` (default `sandbox`), `LOG_LEVEL` (default `INFO`).

---

### kalshi_client.py

**Class: `KalshiClient`** — core API client. Constructor: `KalshiClient(api_key=None, api_secret=None, base_url=None)`. Falls back to `config.py` when args are `None`.

Authentication: RSA-PSS signing per request (timestamp + method + path). Private key loaded from `.pem` file path or inline string.

Retry policy: 3 retries with exponential backoff for 5xx errors; 5 retries for 429 rate limits with `Retry-After` header.

| Method | Signature | Returns | API Endpoint |
|--------|-----------|---------|--------------|
| `get_balance` | `() -> dict` | `{balance, portfolio_value}` in cents | `GET /portfolio/balance` |
| `get_positions` | `(limit=100, cursor=None) -> dict` | `{positions: [...], cursor}` | `GET /portfolio/positions` |
| `get_markets` | `(limit=100, cursor=None, event_ticker=None, series_ticker=None, status=None) -> dict` | `{markets: [...], cursor}` | `GET /markets` |
| `get_market` | `(ticker: str) -> dict` | Market detail dict (may be wrapped in `{"market": {...}}`) | `GET /markets/{ticker}` |
| `place_order` | `(ticker, side, quantity, action="buy", order_type="market", price=None, client_order_id=None, expiration_ts=None) -> dict` | Order dict with `order_id` | `POST /portfolio/orders` |
| `cancel_order` | `(order_id: str) -> dict` | Cancelled order details | `DELETE /portfolio/orders/{id}` |
| `get_order` | `(order_id: str) -> dict` | Order details with status | `GET /portfolio/orders/{id}` |
| `get_orders` | `(ticker=None, status=None, limit=100, cursor=None) -> dict` | `{orders: [...], cursor}` | `GET /portfolio/orders` |
| `get_fills` | `(ticker=None, order_id=None, limit=100, cursor=None) -> dict` | `{fills: [...], cursor}` | `GET /portfolio/fills` |
| `get_settlements` | `(limit=100, cursor=None) -> dict` | `{settlements: [...], cursor}` | `GET /portfolio/settlements` |

Key internal methods: `_make_request(method, endpoint, params, json_data)` handles auth, retries, error parsing. `_sign_request(method, path, timestamp)` produces RSA-PSS signature. `_parse_error_response(response)` handles nested `{"error": {"message": ..., "details": ...}}` format.

---

### trade_executor.py

**Class: `TradeExecutor`** — wrapper for common trade operations. Constructor: `TradeExecutor(client: KalshiClient = None)`.

| Method | Signature | Returns |
|--------|-----------|---------|
| `place_market_order` | `(ticker, side, quantity) -> dict` | Order dict |
| `place_limit_order` | `(ticker, side, quantity, price) -> dict` | Order dict |
| `cancel_order` | `(order_id) -> dict` | Cancelled order dict |
| `get_order_status` | `(order_id) -> dict` | Order status dict |
| `list_open_orders` | `() -> list` | List of resting orders |
| `get_market_info` | `(ticker) -> dict` | Market details (unwrapped) |
| `validate_ticker` | `(ticker) -> bool` | True if market is active/open |
| `search_markets` | `(query=None, status="open", limit=20, series_ticker=None) -> list` | List of matching markets |

Market search iterates `POPULAR_SERIES` (21 series covering crypto, finance, politics, sports, entertainment), deduplicates by ticker, falls back to unfiltered search if no matches.

Private validators: `_validate_side`, `_validate_quantity`, `_validate_price` — raise `TradeExecutionError`.

---

### portfolio_tracker.py

**Class: `PortfolioTracker`** — position and P&L tracking. Constructor: `PortfolioTracker(client: KalshiClient = None)`.

| Method | Signature | Returns |
|--------|-----------|---------|
| `get_current_positions` | `() -> list` | Non-zero positions from API |
| `calculate_position_pnl` | `(pos: dict) -> dict` | `{ticker, title, quantity, side, avg_price, cost, value, pnl, status}` |
| `calculate_total_pnl` | `() -> dict` | `{total_cost, total_value, total_pnl, positions: [...], errors: [...]}` |
| `get_realized_pnl` | `() -> dict` | `{gross_pnl, total_fees, net_pnl, settlements: [...]}` |
| `display_portfolio_summary` | `() -> None` | Prints formatted summary to stdout |

Pricing logic: Active markets use bid/ask midpoint; settled markets use 100c (winner) or 0c (loser); falls back to `last_price` if no bid/ask.

Realized P&L combines two sources: (1) `/portfolio/settlements` for settled markets, (2) FIFO fill matching via `_compute_fill_based_realized_pnl()` for positions sold before settlement. Warns on tickers with both.

Internal pagination: `_paginate(fetch_method, result_keys, error_label)` — generic paginator with `MAX_PAGES=50` safety limit. Tries multiple response keys (e.g. `market_positions` or `positions`).

Helper functions (module-level): `_format_dollars(cents)`, `_format_pnl(cents)`, `_print_position_line(pos)`.

---

### trade_logger.py

**Class: `TradeLogger`** — event logging and history. Constructor: `TradeLogger(log_dir: str = None)` (defaults to `logs/`).

| Method | Signature | Returns |
|--------|-----------|---------|
| `log_order_submission` | `(order_details: dict) -> TradeEvent` | Created event |
| `log_order_fill` | `(fill_details: dict) -> TradeEvent` | Created event |
| `log_order_cancellation` | `(order_id: str) -> TradeEvent` | Created event |
| `log_error` | `(error_message: str, context: dict = None) -> TradeEvent` | Created event |
| `get_trade_history` | `(start_date: datetime = None, end_date: datetime = None) -> list[TradeEvent]` | Filtered events |
| `export_trades_to_csv` | `(filename, start_date=None, end_date=None) -> int` | Row count written |
| `display_recent_trades` | `(count=20) -> None` | Prints to stdout |

**Data types**:
- `TradeEventType` — enum: `SUBMISSION`, `FILL`, `CANCELLATION`, `ERROR`
- `TradeEvent` — dataclass: `event_type, timestamp, order_id, ticker, side, quantity, price, fill_price, quantity_filled, error_message, details`

Storage: dual-write to `trades.log` (human-readable, `TimedRotatingFileHandler`, 30-day retention) and `trades.jsonl` (structured, for querying). Errors also go to `errors.log` (90-day retention). Date filters require timezone-aware datetimes.

---

### cli_interface.py

**Class: `TradingCLI`** — interactive menu loop. Constructor: `TradingCLI(logger: TradeLogger = None)`. Lazy-initializes `TradeExecutor` on first use via `_ensure_executor()`.

Menu options: (1) Search markets, (2) Place market order, (3) Place limit order, (4) View open orders, (5) Cancel order, (6) Check order status, (7) Exit.

Logging: on successful market/limit order placement calls `logger.log_order_submission(result)`; on successful cancellation calls `logger.log_order_cancellation(order_id)`. Logger is optional — skipped gracefully when `None`. Logging exceptions are swallowed so they never crash the trading loop.

Entry point: `run_trading_cli()` or `python3 cli_interface.py`.

Helper functions (module-level): `format_price_dollars(cents)`, `format_order_summary(order)`, `print_header(title)`, `print_market_info(market)`, `get_input(prompt, validator, error_msg)`, `get_int_input(prompt, min_val, max_val)`, `confirm(prompt)`.

## Tests

All tests use `unittest.mock.Mock()` for the KalshiClient — no live API calls in unit tests.

| Test file | Tests | Covers |
|-----------|-------|--------|
| `tests/test_api_client.py` | 25 | KalshiClient (18 unit + 6 integration + 1 other) |
| `tests/test_trade_executor.py` | 40 | TradeExecutor |
| `tests/test_portfolio.py` | 61 | PortfolioTracker |
| `tests/test_trade_logger.py` | 34 | TradeLogger |
| `tests/test_config.py` | 21 | Config loading/validation |
| `tests/test_main.py` | 45 | MainApp (init, menu routing, all action handlers, shutdown) |

Run all: `python3 -m pytest tests/ -v`
Run one module: `python3 -m pytest tests/test_portfolio.py -v`
Integration only: `pytest tests/test_api_client.py -m integration`

### main.py

**Class: `MainApp`** — top-level application controller. Constructor: `MainApp(client=None, executor=None, tracker=None, logger=None)`. Uses dependency injection; creates `KalshiClient` once and shares it with `TradeExecutor` and `PortfolioTracker`.

| Method | Signature | Behaviour |
|--------|-----------|-----------|
| `run` | `() -> None` | Validates config, prints banner, enters menu loop; catches `KeyboardInterrupt` |
| `_view_portfolio` | `() -> None` | Calls `tracker.display_portfolio_summary()`; catches `PortfolioError` + `Exception` |
| `_launch_trading` | `() -> None` | Creates `TradingCLI()` and calls `cli.run()` (full trading sub-menu) |
| `_view_open_orders` | `() -> None` | Calls `executor.list_open_orders()`; formats with `format_order_summary`; catches `TradeExecutionError` |
| `_cancel_order` | `() -> None` | Prompts for order ID, confirms, calls `executor.cancel_order()`; catches `TradeExecutionError` |
| `_view_trade_history` | `() -> None` | Calls `logger.display_recent_trades()`; catches `Exception` |

Module-level entry point: `main()` or `python3 main.py`.

---

## Not Yet Implemented

- Task 7: comprehensive integration testing
