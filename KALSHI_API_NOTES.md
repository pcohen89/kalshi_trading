# Kalshi API Notes: Resolved Market Data

*Researched 2026-02-22. Verify against [Kalshi API docs](https://docs.kalshi.com) if behavior seems off.*

---

## Live vs. Historical API Split

As of **February 19, 2026**, Kalshi split their API into two tiers. Enforced **March 6, 2026**.

- **Live API** (`/markets`, `/events`) — markets settled within ~3 months
- **Historical API** (`/historical/...`) — markets settled more than ~3 months ago

Use `GET /historical/cutoff` to get the exact boundary timestamps.

---

## Key Endpoints for Resolved Markets

| Endpoint | Purpose |
|---|---|
| `GET /markets?status=settled` | Settled markets within the live window |
| `GET /historical/markets` | All markets older than the cutoff (paginated, up to 1,000/page, cursor-based) |
| `GET /historical/markets/{ticker}` | Single historical market object |
| `GET /historical/markets/{ticker}/candlesticks` | OHLC history for a historical market |
| `GET /markets/{ticker}/candlesticks` | OHLC history for a recent market |
| `GET /markets/candlesticks` | Batch OHLC (up to 100 tickers, 10,000 candles/request) |
| `GET /historical/cutoff` | Returns the live/historical boundary timestamps |
| `GET /historical/fills` | Personal fills older than cutoff (auth required) |
| `GET /historical/orders` | Orders older than cutoff (auth required) |

`/historical/markets` filter params: `tickers` (comma-separated), `event_ticker`, `mve_filter`.

---

## Resolved Market Object Fields

### Settlement
| Field | Description |
|---|---|
| `result` | `"yes"`, `"no"`, `"scalar"`, or `""` |
| `settlement_value_dollars` | Payout value of the YES side |
| `settlement_ts` | Timestamp when settled |
| `expiration_value` | Raw measured value that triggered the outcome |
| `status` | `determined` → `disputed` → `amended` → `finalized` |

### Pricing (snapshot at settlement)
| Field | Description |
|---|---|
| `last_price_dollars` | Last traded YES price |
| `yes_bid_dollars`, `yes_ask_dollars` | Final bid/ask on YES side |
| `no_bid_dollars`, `no_ask_dollars` | Final bid/ask on NO side |
| `previous_yes_bid_dollars`, `previous_yes_ask_dollars`, `previous_price_dollars` | 24h-prior prices |

### Volume & Open Interest
| Field | Description |
|---|---|
| `volume_fp` | Total contracts traded (fixed-point) |
| `volume_24h_fp` | Last 24h volume |
| `open_interest_fp` | Outstanding contracts at settlement |

### Metadata
`ticker`, `event_ticker`, `market_type` (`binary`/`scalar`), `title`, `subtitle`, `rules_primary`, `rules_secondary`, `created_time`, `open_time`, `close_time`, `expected_expiration_time`

---

## Candlestick Data

Available at **1-minute, 1-hour, or 1-day** granularity (`period_interval` = 1, 60, or 1440).

Each candle includes:
- `end_period_ts`
- `price`: `open`, `high`, `low`, `close`, `mean`, `previous`
- `yes_bid`, `yes_ask`: OHLC for order book quotes
- `volume` / `volume_fp`
- `open_interest` / `open_interest_fp`

Both integer (cents) and fixed-point dollar string representations are returned for price fields.

---

## Bulk Access

- **No official bulk download** (no CSV dump, no S3)
- Must paginate via REST API
- Batch candlestick endpoint is most efficient for backfilling (100 tickers × 10,000 candles/request)
- Third-party: [DeltaBase](https://www.deltabase.tech/) offers CSV/BigQuery access (paid)
