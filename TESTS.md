# Test Suite — Kalshi Trading System

Agent-readable test map. Covers all 275 tests across 8 files. Before adding new tests, read here to understand what is already covered and which patterns to follow. Only open a test file when you need line-level detail not contained here.

## Running Tests

```bash
python3 -m pytest tests/ -m "not integration" -v   # all mocked tests (268)
python3 -m pytest tests/ -m integration            # live sandbox tests (7, needs .env)
python3 -m pytest tests/test_<module>.py -v        # single file
```

## Test File Inventory

| File | Tests | Module under test | Live API? |
|------|-------|-------------------|-----------|
| `test_api_client.py` | 25 | `KalshiClient` | 7 (marked `integration`) |
| `test_trade_executor.py` | 40 | `TradeExecutor` | no |
| `test_portfolio.py` | 61 | `PortfolioTracker` | no |
| `test_trade_logger.py` | 34 | `TradeLogger` | no |
| `test_config.py` | 21 | `config.py` | no |
| `test_main.py` | 45 | `MainApp` | no |
| `test_cli_interface.py` | 32 | `TradingCLI` | no |
| `test_integration.py` | 17 | cross-module wiring | no |

---

## Shared Patterns

**Fixtures** — each unit-test file defines two module-level fixtures:
```python
@pytest.fixture
def mock_client():          # unittest.mock.Mock()
    return Mock()

@pytest.fixture
def <subject>(mock_client): # subject instantiated with mock client
    return Subject(client=mock_client)
```
Exception: `test_config.py` and `test_trade_logger.py` need no client. `test_trade_logger.py` uses `tmp_path` for an isolated log directory.

**Input simulation** — CLI tests use `patch('builtins.input', side_effect=[...])` where each list item is returned by one `input()` call in order.

**Stdout capture** — `capsys` fixture; `capsys.readouterr().out` after the call.

**Error assertions** — API errors are typically asserted with `pytest.raises(SomeError)` and a substring match on the message string via `str(exc_info.value)`.

**Integration test fixture** — `test_integration.py` builds real module instances sharing one `Mock()` client:
```python
@pytest.fixture
def app(mock_client, tmp_path):
    executor = TradeExecutor(client=mock_client)
    tracker  = PortfolioTracker(client=mock_client)
    logger   = TradeLogger(log_dir=str(tmp_path))
    return MainApp(client=mock_client, executor=executor, tracker=tracker, logger=logger)
```

---

## test_api_client.py

### TestKalshiClientUnit (18 tests — mocked)

Fixture `mock_config` patches `get_api_credentials` and `get_api_base_url`, generates a real RSA key in-process so `_private_key` loads without a `.pem` file.

| Test | What it checks |
|------|----------------|
| `test_client_initialization` | `api_key`, `base_url`, `_private_key` set correctly |
| `test_request_signing` | `_sign_request` returns valid base64 |
| `test_auth_headers_generation` | `_get_auth_headers` produces all three KALSHI-* headers |
| `test_place_order_validation_limit_no_price` | `KalshiAPIError` if limit order has `price=None` |
| `test_place_order_validation_invalid_side` | `KalshiAPIError` for side not in ("yes","no") |
| `test_place_order_validation_invalid_action` | `KalshiAPIError` for action not in ("buy","sell") |
| `test_place_order_validation_negative_quantity` | `KalshiAPIError` for quantity < 0 |
| `test_place_order_validation_zero_quantity` | `KalshiAPIError` for quantity == 0 |
| `test_place_order_validation_price_too_high` | `KalshiAPIError` for price > 99 |
| `test_place_order_validation_price_too_low` | `KalshiAPIError` for price < 1 |
| `test_retry_on_server_error` | 500→500→200: retries twice, succeeds on third |
| `test_no_retry_on_401` | 401: single call, raises `KalshiAPIError` with `status_code=401` |
| `test_rate_limit_handling` | 429→200: waits, retries, succeeds |
| `test_error_parsing` | 400 with `{"message": ...}` body → exception with that message |
| `test_204_no_content` | `cancel_order` with 204 response returns `{}` |

### TestKalshiAPIError (3 tests)

Checks `str(error)` formatting with/without status code; `response_body` attribute stored correctly.

### TestKalshiClientIntegration (7 tests — `@pytest.mark.integration`)

Live sandbox tests requiring valid `.env`. Cover `get_balance`, `get_positions`, `get_markets`, `get_market`, `get_orders`, `get_fills`, `get_settlements`. Skipped by default (`-m "not integration"`).

---

## test_trade_executor.py

Fixture: `executor = TradeExecutor(client=mock_client)`.

### TestPlaceMarketOrder (8 tests)
Success for yes/no sides; `TradeExecutionError` for invalid side (wrong string, empty), invalid quantity (zero, negative, float), API error (`"Failed to place market order"` in message).

### TestPlaceLimitOrder (8 tests)
Success; `TradeExecutionError` for price < 1, price > 99, `price=None`, float price; accepts edge prices 1 and 99; API error (`"Failed to place limit order"`).

### TestCancelOrder (3 tests)
Success returns order dict; `KalshiAPIError` wrapped as `TradeExecutionError` (`"Failed to cancel order"`).

### TestGetOrderStatus (3 tests — implied from coverage)
Success, empty order_id, API error (`"Failed to get order status"`).

### TestListOpenOrders (3 tests)
Calls `client.get_orders(status="resting")`, returns `result["orders"]`; empty list; `KalshiAPIError` → `TradeExecutionError` (`"Failed to list open orders"`).

### TestGetMarketInfo (3 tests)
Success unwraps `{"market": {...}}`; empty ticker → `"Ticker cannot be empty"`; not found → `"Failed to get market info"`.

### TestValidateTicker (3 tests)
Open market → `True`; closed market → `False`; 404 → `False` (no exception).

### TestSearchMarkets (8 tests)
No query returns all; query filters by title and ticker (case-insensitive); no matches returns `[]`; respects `limit`; passes `series_ticker` to `client.get_markets`; API error → `"Failed to search markets"`.

---

## test_portfolio.py

Fixture: `tracker = PortfolioTracker(client=mock_client)`.

Mock convention: `mock_client.get_positions.return_value = {"market_positions": [...], "cursor": ""}` (also accepts `"positions"` key). Paginate with `side_effect=[page1_dict, page2_dict]`.

### TestHelperFunctions (6 tests)
`_format_dollars`: positive, zero, `None`, negative (uses abs). `_format_pnl`: positive (`+$`), negative (`-$`), zero (`+$0.00`), `None`.

### TestGetCurrentPositions (7 tests)
Filters `position == 0`; empty list; single-page pagination; multi-page pagination (cursor loop); accepts `"positions"` key; `KalshiAPIError` → `PortfolioError("Failed to fetch positions")`; missing `position` key treated as 0.

### TestCalculatePositionPnl (11 tests)
Pricing: active market → `(yes_bid + yes_ask) // 2`; settled YES win → 100c per contract; settled YES lose → 0c; settled NO win/lose (mirror); fallback to `last_price` when bid/ask are 0; fallback to 0 when all zero; `KalshiAPIError` → `PortfolioError("Failed to get market price")`; handles response without `"market"` wrapper key.

### TestCalculateTotalPnl (5 tests)
Aggregates across positions; empty portfolio returns zeros; skips failed positions (records ticker in `result["errors"]`); all fail → zeros + all tickers in errors; `PortfolioError` from position fetch propagates.

### TestGetRealizedPnl (6 tests — settlement-only scenarios)
Aggregates settlements (gross_pnl, total_fees, net_pnl); no-cost settlement; both yes+no cost; empty settlements → zeros; `KalshiAPIError` → `PortfolioError`; settlement entries have `source="settlement"`.

### TestDisplayPortfolioSummary (5 tests)
Calls `get_balance`, `get_positions`, `get_settlements`, `get_fills`. Checks stdout for: "Portfolio Summary" + dollar amounts; "No open positions"; ticker + title when position exists; "Realized P&L" section; "NOTE:" / "estimated from fill data" when fill-sourced entries exist.

### TestFetchAllFills / TestFetchAllSettlements (3+3 tests)
Single-page fetch; multi-page pagination; `KalshiAPIError` → `PortfolioError`.

### TestFillBasedRealizedPnl (11 tests)
YES round-trip profit/loss; NO round-trip profit; partial sell (only matched contracts count); loss; FIFO matching (multiple buy lots); sell fees deducted from net; fills + settlements on different tickers both counted; overlapping ticker → settlement takes precedence, fill-based skipped; buy-only fills produce no P&L; empty → zeros; ambiguous tickers (both settlement and sell fills) → WARNING printed to stdout.

---

## test_trade_logger.py

Fixture: `logger = TradeLogger(log_dir=str(tmp_path))`.

### TestLogOrderSubmission (5 tests)
Returns `TradeEvent` with correct fields; handles unwrapped order dict; writes to `trades.jsonl`; writes to `trades.log`; timestamp is timezone-aware UTC.

### TestLogOrderFill (3 tests)
Returns `TradeEvent` with `fill_price` and `quantity_filled`; writes to jsonl; handles `fill_price`/`quantity_filled` fallback keys.

### TestLogOrderCancellation (2 tests)
Returns `TradeEvent(event_type="cancellation", order_id=...)`; writes to jsonl.

### TestLogError (4 tests)
Returns `TradeEvent` with `error_message`; writes to `errors.log`; also writes to jsonl; context dict stored in `details`.

### TestGetTradeHistory (7 tests)
Returns all events; `start_date` filter (future → empty); `end_date` filter (past → empty); date range filter; empty file → `[]`; naive `start_date` → `TradeLoggerError("start_date must be timezone-aware")`; naive `end_date` → `TradeLoggerError`.

### TestDisplayRecentTrades (3 tests)
Prints event type ("submission") and ticker; respects `count` limit (header + separator + N data lines); empty log → `"No trade events recorded"`.

### CSV export tests (~7 tests)
`export_trades_to_csv` writes correct columns (`CSV_COLUMNS`), returns row count, respects date filters, handles empty history.

### TestLoggerSetup (~3 tests)
Creates log directory if missing; creates both `trades.log` and `errors.log` on first use; `trades.jsonl` created on first event.

---

## test_config.py

No fixtures. Uses `@patch.dict(os.environ, {...}, clear=True)` to isolate each test.

Helper constants: `VALID_ENV = {"KALSHI_API_KEY": "test_key_abc123", "KALSHI_API_SECRET": "test_secret_xyz789"}`, `VALID_ENV_PRODUCTION` adds `"KALSHI_ENVIRONMENT": "production"`.

### TestGetRequired (4 tests)
Returns value when set; `ConfigurationError("Missing required configuration: KEY")` when missing or empty; same error for placeholder value starting with `"your_"`.

### TestGetOptional (2 tests)
Returns value when set; returns default when key absent.

### TestGetConfig (8 tests)
Valid env → dict with `api_key, api_secret, environment, log_level, api_base_url`; missing `KALSHI_API_KEY` or `KALSHI_API_SECRET` → `ConfigurationError`; invalid environment (`"staging"`) → `"Invalid KALSHI_ENVIRONMENT"`; invalid log level (`"TRACE"`) → `"Invalid LOG_LEVEL"`; defaults to sandbox + INFO.

### TestConvenienceFunctions (7 tests)
`get_api_credentials` → `(key, secret)` tuple; `get_api_base_url` → URL string matching `API_URLS["sandbox"]`; `get_environment` → `"sandbox"`; `get_log_level` → `"INFO"`; `is_production` → `True`/`False`; `validate_config` → `True`.

---

## test_main.py

Fixture: `app = MainApp(client=Mock(), executor=Mock(), tracker=Mock(), logger=Mock())`.

### TestMainAppInit (7 tests)
`MainApp()` with no args creates `KalshiClient`, passes it to `TradeExecutor(client=...)` and `PortfolioTracker(client=...)`; accepts injected deps; does not create `KalshiClient` when one is injected.

### TestMainAppMenuRouting (8 tests)
Choices 1–5 each route to their handler (patched with `patch.object`); choice 6 exits without calling any handler; invalid choice prints error and continues; multiple choices all routed in one `run()` call. Pattern: `patch("builtins.input", side_effect=["N", "6"])` + `patch("main.validate_config")`.

### TestViewPortfolio (5 tests)
Calls `tracker.display_portfolio_summary()`; returns `None`; catches `PortfolioError` and prints; catches `RuntimeError` and prints; error message is non-empty.

### TestViewOpenOrders (6 tests)
Calls `executor.list_open_orders()`; empty list → prints "no"/"order"; calls `format_order_summary` once per order; prints each formatted line; catches `TradeExecutionError`; returns `None`.

### TestCancelOrder (7 tests)
Calls `executor.cancel_order(order_id)` on confirmation; prints success; empty/whitespace input returns early without calling cancel; declined confirmation skips cancel; `TradeExecutionError` caught and printed; returns `None`.

### TestViewTradeHistory (5 tests)
Calls `logger.display_recent_trades()`; returns `None`; catches any exception and prints; does not touch executor or tracker.

### TestShutdownAndEntryPoint (7 tests)
`ConfigurationError` from `validate_config` → prints error, returns without entering menu loop (`input` not called); `KeyboardInterrupt` from `input` → handled, prints "Goodbye"; `main()` creates `MainApp` and calls `run()`; `main()` handles `KeyboardInterrupt` from `run()`.

---

## test_cli_interface.py

Helper: `_cli_with_mock_executor()` → `TradingCLI()` with `cli.executor = Mock()` pre-set to bypass lazy init.

### TestTradingCLIInit (3 tests)
`executor` is `None` on construction; `_ensure_executor()` calls `TradeExecutor()` (no args), assigns result, returns `True`; second call reuses the same instance (`TradeExecutor` called only once).

### TestSearchMarkets (3 tests)
Inputs `["query", "1"]`; returns markets list → ticker in stdout. Inputs `["", "1"]`; empty results → "No markets found" in stdout. `TradeExecutionError` from `search_markets` caught → "Error" in stdout.

### TestPlaceMarketOrder (4 tests)
Inputs `["TICKER", "yes", "5", "yes"]`; `place_market_order("TICKER", "yes", 5)` called; `order_id` in stdout. Inputs `[..., "n"]` → `place_market_order` not called. Input `"maybe"` for side → error printed, not called. `TradeExecutionError` from `place_market_order` caught.

### TestPlaceLimitOrder (4 tests)
Inputs `["TICKER", "yes", "5", "50", "yes"]` → `place_limit_order("TICKER", "yes", 5, 50)` called. Inputs `[..., "0", "50", "yes"]` → price=0 rejected with bounds error, price=50 accepted. Inputs `[..., "n"]` → not called. API error caught.

### TestViewOpenOrders (3 tests)
Orders list → order_id in stdout (via `format_order_summary`, truncated to 12 chars). Empty → "No open orders". `TradeExecutionError` caught.

### TestCancelOrder (3 tests)
Inputs `["ord-id", "yes"]` → `cancel_order("ord-id")` called. Inputs `[..., "n"]` → not called. `TradeExecutionError` caught.

### TestCheckOrderStatus (2 tests)
Inputs `["ord-id"]` → `get_order_status` called, order_id in stdout. `TradeExecutionError` caught.

### TestMenuLoop (3 tests)
Inputs `["invalid", "7"]` → "Invalid" in stdout. Inputs `["7"]` → `run()` returns. `run_trading_cli()` with `KeyboardInterrupt` from `input` → "Interrupted"/"Goodbye" in stdout, no exception raised.

### TestLogging (7 tests — Task 8)
Helper `_cli_with_mock_executor_and_logger()` → `TradingCLI(logger=mock_logger)` with mock executor pre-set.

`test_place_market_order_logs_submission_on_success` — `logger.log_order_submission(result)` called with full order result dict.
`test_place_market_order_no_logger_does_not_crash` — `logger=None` (default), order placed without crash.
`test_place_market_order_logger_error_does_not_propagate` — `log_order_submission` raises `RuntimeError`; no exception escapes.
`test_place_limit_order_logs_submission_on_success` — same as market order variant for limit path.
`test_place_limit_order_no_logger_does_not_crash` — `logger=None`, no crash.
`test_cancel_order_logs_cancellation_on_success` — `logger.log_order_cancellation(order_id)` called with the order id string.
`test_cancel_order_no_logger_does_not_crash` — `logger=None`, no crash.

---

## test_integration.py

Fixture: `app(mock_client, tmp_path)` — real `TradeExecutor`, `PortfolioTracker`, `TradeLogger` instances sharing one `mock_client`.

### TestDependencyInjection (3 tests)
`app.executor.client is mock_client`; `app.tracker.client is mock_client`; TradingCLI's lazily-created executor is a different object from `app.executor`.

### TestPortfolioPath (2 tests)
`_view_portfolio()` delegates to `app.tracker.display_portfolio_summary` (verified via `patch.object`). `PortfolioError` raised by tracker → caught, error in stdout, menu continues.

### TestOpenOrdersPath (2 tests)
`mock_client.get_orders.return_value = {"orders": [...]}` flows through real executor to formatted stdout (asserts on ticker, not truncated order_id). `TradeExecutionError` from `list_open_orders` caught.

### TestCancelOrderPath (2 tests)
Confirmed cancel flows through real executor → `mock_client.cancel_order` called with correct id. `TradeExecutionError` caught.

### TestTradeHistoryPath (2 tests)
`app.logger.log_order_submission(...)` then `_view_trade_history()` → ticker visible in stdout. Fresh logger (empty dir) → "No trade events recorded".

### TestErrorRecovery (2 tests)
Three-step sequence (portfolio error → orders error → success) via `side_effect` iterables on `patch.object` — menu stays alive throughout. `ConfigurationError` from `validate_config` → error printed, `input` never called.

### TestMenuRouting (2 tests)
Choices "1" and "5" with `patch.object(app, '_view_portfolio')` / `patch.object(app, '_view_trade_history')` confirm routing works on a real `MainApp` instance.

### TestTradeLoggingPath (2 tests — Task 8)
`test_launch_trading_passes_logger_to_cli` — patches `main.TradingCLI`; asserts it is constructed with `logger=app.logger`.
`test_order_placed_via_cli_appears_in_trade_history` — real `TradingCLI(logger=app.logger)` with mock executor drives `_place_market_order`; then `app._view_trade_history()` → ticker visible in stdout.

---

## Known Gaps

- Integration tests for `TestPortfolioPath` use `patch.object` on `display_portfolio_summary` rather than driving through full client mock setup. Full end-to-end portfolio display is covered in `test_portfolio.py::TestDisplayPortfolioSummary`.
