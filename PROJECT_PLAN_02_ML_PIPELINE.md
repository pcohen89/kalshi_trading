# Kalshi Trading System — V2 ML Pipeline

> **STATUS: PLANNED ⏳**
> Builds on the V1 core infrastructure (PROJECT_PLAN_01). All 275 V1 tests remain green throughout.
> Covers: historical data collection → EDA → gradient boosting → model evaluation → active market scoring.

---

## Project Overview

### Objective
Build an end-to-end ML workflow that ingests historical Kalshi market data, discovers behavioural patterns through EDA, trains a gradient boosting model to predict next-day YES prices, evaluates it rigorously, and surfaces recommended contract purchases for active markets.

### Prediction Target
Next-day YES price (regression, 0–99 cents). Edge = predicted_price − current_price. Recommendations are ranked by absolute edge size.

### Data Scope
~6 months of settled markets across the 21 popular series already tracked in `trade_executor.POPULAR_SERIES`. Expected ~1,000–3,000 settled markets, ~540,000 daily candle rows total.

### Success Criteria
- `python3 ml/ml_pipeline.py collect` completes without crashing and writes `data_store/markets.csv` + `data_store/candles.csv`
- Model test MAE < 10 cents (random baseline ≈ 25 cents for uniform prices)
- `python3 ml/ml_pipeline.py recommend` prints a formatted recommendation table for live markets
- All new tests pass alongside the existing 275: `python3 -m pytest tests/ -m "not integration" -v`

### Urgency Note
Kalshi enforces the live/historical API split on **March 6, 2026**. All data collection code must handle both endpoints from day one.

### Out of Scope for V2
- Automated order execution from recommendations (still manual)
- External data sources (news, social sentiment)
- Real-time/streaming price updates
- Portfolio-level risk management and position sizing rules
- Model retraining scheduler

---

## Task Overview

| Task | Description | New Tests | Status |
|------|-------------|-----------|--------|
| 9  | Extend KalshiClient with historical + candlestick endpoints | ~15 | ⏳ Pending |
| 10 | DataStore — CSV persistence layer | ~15 | ⏳ Pending |
| 11 | DataCollector — market + candle ingestion | ~15 | ⏳ Pending |
| 12 | EDA Notebooks — behavioural pattern analysis | 0 (notebooks) | ⏳ Pending |
| 13 | FeatureEngineer — (ticker, day) feature matrix | ~20 | ⏳ Pending |
| 14 | ModelTrainer — XGBoost regression with time-based split | ~15 | ⏳ Pending |
| 15 | ModelEvaluator — metrics + by-category breakdown | ~10 | ⏳ Pending |
| 16 | MarketScorer — score active markets, generate recommendations | ~15 | ⏳ Pending |
| 17 | MLPipeline CLI — argparse orchestrator + end-to-end run | ~5 | ⏳ Pending |

---

## Data Conventions (Cross-Cutting)

These apply across all tasks. Agents should not need to infer these.

### Timestamps
- **API inputs** (`start_ts`, `end_ts`): Unix epoch **seconds** as `int`. Compute with `int(datetime.now().timestamp())`.
- **CSV storage** (`open_time`, `close_time`, `settlement_ts`, `period_end_ts`): **ISO8601 strings** (`"2025-12-01T18:00:00Z"`). Store and compare as strings via `pd.to_datetime()`.
- **Conversion**: `int(pd.to_datetime(iso_str).timestamp())` to get epoch seconds from an ISO string.

### Prices
- All prices stored and used internally in **cents (int)**, including in CSV files and the feature matrix.
- API market fields include both: `settlement_value_dollars` (float dollars) → multiply by 100 and round to get `settlement_value_cents`.
- Candle price fields: the API returns both integer cents fields and dollar string fields. **Use the integer fields** (e.g., `price.open` is cents).

### Candle JSON shape
Each candle object from the API looks like:
```json
{
  "end_period_ts": 1701388800,
  "price":   {"open": 42, "high": 55, "low": 38, "close": 51, "mean": 46, "previous": 40},
  "yes_bid": {"open": 41, "high": 54, "low": 37, "close": 50},
  "yes_ask": {"open": 43, "high": 56, "low": 39, "close": 52},
  "volume": 1200,
  "open_interest": 3400
}
```
Flatten to CSV columns: `period_end_ts` (ISO8601 from epoch), `open_cents=price.open`, `high_cents=price.high`, `low_cents=price.low`, `close_cents=price.close`, `volume`, `open_interest`, `yes_bid_cents=yes_bid.close`, `yes_ask_cents=yes_ask.close`.

### API market field mapping → CSV column names
| API field | CSV column | Notes |
|-----------|-----------|-------|
| `ticker` | `ticker` | |
| `event_ticker` | `event_ticker` | |
| `series_ticker` | `series_ticker` | |
| `title` | `title` | |
| `market_type` | `market_type` | `"binary"` or `"scalar"` |
| `status` | `status` | `"open"`, `"settled"`, etc. |
| `result` | `result` | `"yes"`, `"no"`, `"scalar"`, `""` |
| `settlement_value_dollars` | `settlement_value_cents` | multiply by 100 |
| `open_time` | `open_time` | ISO8601 string |
| `close_time` | `close_time` | ISO8601 string |
| `settlement_ts` | `settlement_ts` | ISO8601 string (may be empty) |
| *(set at collect time)* | `collected_at` | `datetime.now(timezone.utc).isoformat()` |

### .gitignore additions required
Add these entries before committing:
```
data_store/
models/*.pkl
```

---

## New Directory Structure

Files added on top of V1. Existing files (`kalshi_client.py`, `trade_executor.py`, etc.) are either untouched or extended.

```
kalshi_trading/
├── kalshi_client.py          ← EXTEND: 4 new methods (Tasks 9)
│
├── data/
│   ├── __init__.py
│   ├── data_store.py         ← NEW (Task 10)
│   └── data_collector.py     ← NEW (Task 11)
│
├── ml/
│   ├── __init__.py
│   ├── feature_engineer.py   ← NEW (Task 13)
│   ├── model_trainer.py      ← NEW (Task 14)
│   ├── model_evaluator.py    ← NEW (Task 15)
│   ├── market_scorer.py      ← NEW (Task 16)
│   └── ml_pipeline.py        ← NEW (Task 17)
│
├── eda/
│   ├── 01_data_overview.ipynb        ← NEW (Task 12)
│   ├── 02_behavioral_patterns.ipynb  ← NEW (Task 12)
│   └── 03_price_dynamics.ipynb       ← NEW (Task 12)
│
├── models/                   ← gitignored; holds .pkl artifacts
│   └── .gitkeep
│
├── data_store/               ← gitignored; holds markets.csv + candles.csv
│   └── .gitkeep
│
├── tests/
│   ├── (275 existing tests — unchanged)
│   ├── test_data_store.py          ← NEW (Task 10)
│   ├── test_data_collector.py      ← NEW (Task 11)
│   ├── test_feature_engineer.py    ← NEW (Task 13)
│   ├── test_model_trainer.py       ← NEW (Task 14)
│   ├── test_model_evaluator.py     ← NEW (Task 15)
│   ├── test_market_scorer.py       ← NEW (Task 16)
│   └── test_ml_pipeline.py         ← NEW (Task 17)
│
└── requirements_ml.txt       ← NEW: ML-specific dependencies
```

---

## New Dependencies (`requirements_ml.txt`)

```
pandas>=2.0.0
numpy>=1.24.0
xgboost>=2.0.0
scikit-learn>=1.3.0
joblib>=1.3.0
matplotlib>=3.7.0
seaborn>=0.12.0
jupyter>=1.0.0
```

Install: `pip install -r requirements_ml.txt`

---

## Task 9: Extend KalshiClient with Historical + Candlestick Endpoints

**File**: `kalshi_client.py`
**Status**: ⏳ Pending

### Why
`KalshiClient` has no support for `/historical/` endpoints or any candlestick endpoint. The data collector needs both. All API logic lives in `KalshiClient` by convention.

### What to implement

Add 4 methods inside `KalshiClient`, following the existing `_make_request` pattern:

```python
def get_historical_cutoff(self) -> dict:
    """Return the live/historical boundary timestamps.

    Endpoint: GET /historical/cutoff
    Returns: {"live_cutoff_ts": int, "historical_cutoff_ts": int}
    """

def get_historical_markets(
    self,
    limit: int = 1000,
    cursor: Optional[str] = None,
    series_ticker: Optional[str] = None,
    event_ticker: Optional[str] = None,
) -> dict:
    """Fetch markets older than the historical cutoff.

    Endpoint: GET /historical/markets
    Params differ from get_markets(): no status filter (all are settled);
    supports series_ticker and event_ticker filters.
    Returns: {"markets": [...], "cursor": str}
    """

def get_market_candlesticks(
    self,
    ticker: str,
    period_interval: int = 1440,
    start_ts: Optional[int] = None,
    end_ts: Optional[int] = None,
    historical: bool = False,
) -> dict:
    """Fetch OHLC candlesticks for a single market.

    historical=False → GET /markets/{ticker}/candlesticks
    historical=True  → GET /historical/markets/{ticker}/candlesticks
    Params are identical; only the URL path differs.
    period_interval: 1 (minute), 60 (hour), 1440 (day).
    Returns: {"candlesticks": [...]}
    """

def get_batch_candlesticks(
    self,
    tickers: list[str],
    period_interval: int = 1440,
    start_ts: Optional[int] = None,
    end_ts: Optional[int] = None,
) -> dict:
    """Fetch OHLC candlesticks for up to 100 live tickers in one call.

    Endpoint: GET /markets/candlesticks
    tickers passed as comma-separated query param.
    Only works for live (non-historical) markets.
    Returns: {"candlesticks": {ticker: [...]}}
    """
```

**Routing rationale**: `get_market_candlesticks` uses a single `historical` flag because the params are identical — only the URL path changes. Market listing stays as two separate methods (`get_markets` / `get_historical_markets`) because the params genuinely differ: `get_historical_markets` has no `status` filter and accepts a comma-separated `tickers` param.

### Candle object fields (from API)
See **Data Conventions → Candle JSON shape** above for the exact JSON structure and how to flatten it to CSV columns.

### Inputs / Outputs

| Method | Input | Output |
|--------|-------|--------|
| `get_historical_cutoff` | none | `{"live_cutoff_ts": int, "historical_cutoff_ts": int}` (epoch seconds) |
| `get_historical_markets` | limit, cursor, series_ticker, event_ticker | `{"markets": [...], "cursor": str}` |
| `get_market_candlesticks` | ticker, period_interval, start_ts, end_ts, historical | `{"candlesticks": [...]}` |
| `get_batch_candlesticks` | tickers (list), period_interval, start_ts, end_ts | `{"candlesticks": {ticker: [...]}}` |

**`start_ts` / `end_ts`**: Unix epoch seconds (int). Pass as query params. Example: `start_ts=int((datetime.now() - timedelta(days=180)).timestamp())`.

**`get_batch_candlesticks` tickers param**: The API expects a single `tickers` query param with comma-separated values, e.g. `tickers=KXBTC-24DEC31-T97000,KXETH-25JAN15-T3000`. In `_make_request` params dict: `{"tickers": ",".join(tickers), "period_interval": period_interval, ...}`.

**`get_historical_markets` additional param**: Optionally accepts `tickers` (comma-separated list of specific tickers to fetch). This is not in the class signature above — add `tickers: Optional[list[str]] = None` and join to a comma-separated string if provided.

### Implementation notes
- Follow the same pattern as the existing `get_markets` method: build a `params` dict, pass to `self._make_request("GET", endpoint, params=params)`.
- For `get_market_candlesticks`, the only difference between `historical=True` and `historical=False` is the endpoint string: `f"/markets/{ticker}/candlesticks"` vs `f"/historical/markets/{ticker}/candlesticks"`.
- These methods are tested by mocking `self._make_request` — the existing test file `tests/test_api_client.py` already has the `mock_config` and `client` fixtures to reuse.

### Tests (`tests/test_api_client.py` — extend existing file)
~15 new unit tests mocking `_make_request`:
- `get_historical_cutoff` — returns dict correctly
- `get_historical_markets` — passes series_ticker param; cursor pagination
- `get_market_candlesticks(historical=False)` — correct path
- `get_market_candlesticks(historical=True)` — correct historical path
- `get_batch_candlesticks` — comma-separates tickers; handles 100-ticker batch
- API errors on each new method raise `KalshiAPIError`

---

## Task 10: DataStore — CSV Persistence Layer

**File**: `data/data_store.py`
**Status**: ⏳ Pending

### Why
No local persistence exists in V1. The ML pipeline needs a local store to: avoid re-fetching the same data, share data between pipeline steps, and support EDA notebook exploration.

### Storage format: two CSV files
At ~540,000 candle rows, pandas loads a flat CSV in milliseconds — no database needed. Two files:
- `data_store/markets.csv` — one row per market, keyed on `ticker`
- `data_store/candles.csv` — one row per (ticker, period_end_ts, granularity)

### CSV columns

**markets.csv**:
`ticker, event_ticker, series_ticker, title, market_type, status, result, settlement_value_cents, open_time, close_time, settlement_ts, collected_at`

**candles.csv**:
`ticker, period_end_ts, granularity, open_cents, high_cents, low_cents, close_cents, volume, open_interest, yes_bid_cents, yes_ask_cents`

All monetary values stored in cents. Timestamps stored as ISO8601 strings.

### Class

```python
class DataStore:
    MARKETS_PATH = "data_store/markets.csv"
    CANDLES_PATH = "data_store/candles.csv"

    def __init__(
        self,
        markets_path: str = MARKETS_PATH,
        candles_path: str = CANDLES_PATH,
    ) -> None

    def save_markets(self, markets: list[dict]) -> int
    # Appends to markets.csv; deduplicates on ticker (keep last); rewrites.
    # Returns count of newly added rows.

    def save_candles(self, ticker: str, candles: list[dict], granularity: int) -> int
    # Appends to candles.csv; deduplicates on (ticker, period_end_ts, granularity).
    # Returns count of newly added rows.

    def get_markets(
        self,
        series_ticker: str = None,
        status: str = None,
    ) -> pd.DataFrame

    def get_candles(self, ticker: str = None) -> pd.DataFrame

    def ticker_has_candles(self, ticker: str) -> bool

    def get_collected_tickers(self) -> set[str]
    # Set of tickers that already have candles — used for checkpointing.
```

`DataStoreError` inherits from `Exception`.

### Implementation notes

**Directory creation**: `__init__` must create the parent directory if it doesn't exist:
```python
from pathlib import Path
Path(self.markets_path).parent.mkdir(parents=True, exist_ok=True)
```

**API field mapping**: See **Data Conventions → API market field mapping** above for the exact field names and conversions required before saving. `settlement_value_dollars` from the API must be multiplied by 100 and stored as `settlement_value_cents` (int).

**Candle field extraction**: Candle rows arrive as nested dicts. Extract to flat columns as shown in **Data Conventions → Candle JSON shape**. The `ticker` argument passed to `save_candles` tags each row since candle objects don't always include the ticker.

**Upsert semantics**: Load existing CSV (if it exists), concatenate with new rows, call `drop_duplicates(subset=key_cols, keep='last')`, rewrite. "Newly added rows" = rows in new data whose key was not already in the existing CSV before the call. Return this count.

**`save_candles` return value**: Return `len(new_rows)` where `new_rows` is filtered to only rows whose `(ticker, period_end_ts, granularity)` composite key was absent from the file before this call.

**Empty file handling**: If CSV doesn't exist yet, `get_markets()` / `get_candles()` should return an empty DataFrame with the correct columns (don't raise an error).

### Tests (`tests/test_data_store.py`)
~15 tests using `tmp_path` fixture for CSV isolation:
- `save_markets` creates file on first call
- `save_markets` upserts (duplicate ticker → overwrites, not appended)
- `save_candles` upserts on (ticker, period_end_ts, granularity)
- `get_markets` filters by series_ticker and status
- `get_candles` filters by ticker
- `ticker_has_candles` returns False when file absent or ticker missing
- `get_collected_tickers` returns correct set

---

## Task 11: DataCollector — Market + Candle Ingestion

**File**: `data/data_collector.py`
**Status**: ⏳ Pending

### Why
Orchestrates the full data pull across both live and historical API endpoints, with checkpointing to avoid re-fetching and resilient error handling per ticker.

### Live vs Historical routing

| Market age | Market listing endpoint | Candle endpoint |
|------------|------------------------|-----------------|
| settled < ~3 months | `GET /markets?status=settled` | `GET /markets/candlesticks` (batch, 100/call) |
| settled > ~3 months | `GET /historical/markets` | `GET /historical/markets/{ticker}/candlesticks` (per ticker) |

Boundary determined by `GET /historical/cutoff`, cached after first call.

### Class

```python
@dataclass
class CollectionSummary:
    markets_found: int
    markets_new: int
    tickers_with_candles: int
    candles_collected: int
    errors: list[str]

class DataCollector:
    BATCH_SIZE = 100  # max tickers per batch candlestick call

    def __init__(
        self,
        client: KalshiClient = None,
        store: DataStore = None,
    ) -> None

    def get_cutoff_ts(self) -> int
    # Calls client.get_historical_cutoff(); caches result.

    def collect_settled_markets(
        self,
        series_tickers: list[str] = None,
        days_back: int = 180,
    ) -> list[dict]
    # Fetches from BOTH get_markets(status="settled") AND
    # get_historical_markets() for each series ticker.
    # Filters to close_time >= now - days_back.
    # Saves to store. Returns deduplicated combined list.

    def collect_candlesticks(
        self,
        tickers: list[str],
        granularity: int = 1440,
        days_back: int = 180,
    ) -> dict[str, int]
    # Skips tickers already in store.get_collected_tickers() (checkpointing).
    # Splits remaining tickers into:
    #   live: settlement_ts > cutoff → batch via get_batch_candlesticks()
    #   historical: settlement_ts <= cutoff → per-ticker via get_market_candlesticks(historical=True)
    # Continues past individual ticker errors (logs error, moves on).
    # Returns {ticker: candle_count}.

    def run(
        self,
        series_tickers: list[str] = None,
        days_back: int = 180,
    ) -> CollectionSummary
    # Full orchestration: markets → candles → print summary.
    # series_tickers defaults to trade_executor.POPULAR_SERIES.
```

`DataCollectionError` inherits from `Exception`.

### Implementation notes

**Live vs historical routing for candles**: Determine using the `settlement_ts` field from the markets CSV. If `settlement_ts` is non-empty, parse to epoch seconds and compare to `get_cutoff_ts()`. If `settlement_ts` is empty (market hasn't fully settled yet), use `close_time` as the proxy. Markets with timestamp > cutoff → live endpoint (batch); ≤ cutoff → historical endpoint (per ticker).

**Computing `start_ts` / `end_ts`**:
```python
from datetime import datetime, timedelta, timezone
end_ts = int(datetime.now(timezone.utc).timestamp())
start_ts = int((datetime.now(timezone.utc) - timedelta(days=days_back)).timestamp())
```

**Batching live tickers**: `get_batch_candlesticks` accepts max 100 tickers per call. Chunk the list:
```python
for i in range(0, len(live_tickers), self.BATCH_SIZE):
    batch = live_tickers[i : i + self.BATCH_SIZE]
    result = self.client.get_batch_candlesticks(batch, ...)
```

**Checkpointing**: Before collecting candles, call `store.get_collected_tickers()` once. Exclude those tickers from both the live and historical batches. This allows re-running `collect` after a partial failure without re-fetching already-collected data.

**Progress output format**:
```
[collect] Series KXBTC: 45 markets found
[collect] Fetching candles: 120/450 tickers done (45 live batch, 75 historical per-ticker)
[collect] Done. Markets: 1,234 total (890 new). Candles: 234,000 rows. Errors: 3 tickers skipped.
```

**Error tolerance**: Wrap each per-ticker historical candle call in `try/except KalshiAPIError`. Log the error with the ticker name and append `f"{ticker}: {e}"` to the errors list. Continue to the next ticker.

### Tests (`tests/test_data_collector.py`)
~15 tests mocking `KalshiClient` methods:
- `get_cutoff_ts` caches result (only one API call for multiple invocations)
- `collect_settled_markets` calls both live and historical endpoints per series
- `collect_settled_markets` filters by date (closes before days_back window excluded)
- `collect_candlesticks` skips tickers already in store
- `collect_candlesticks` routes live tickers to batch endpoint
- `collect_candlesticks` routes historical tickers to per-ticker endpoint
- `collect_candlesticks` continues when individual ticker raises `KalshiAPIError`
- `run` returns correct `CollectionSummary`

---

## Task 12: EDA Notebooks

**Directory**: `eda/`
**Status**: ⏳ Pending (run after Task 11 populates data)

Three Jupyter notebooks. Each starts by loading `DataStore` and reading into DataFrames. Findings inform feature selection for Task 13.

### Standard setup cell (first cell in every notebook)
```python
import sys
sys.path.insert(0, '..')          # so `from data.data_store import DataStore` works

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns

from data.data_store import DataStore

store = DataStore()
markets_df = store.get_markets()
candles_df = store.get_candles()

# Add category column for grouping
CATEGORY_MAP = {
    "KXBTC": "crypto", "KXETH": "crypto",
    "INXD": "financial", "KXFED": "financial", "KXCPI": "financial",
    "KXGDP": "financial", "KXJOBS": "financial", "KXRATE": "financial",
    "PRES": "politics", "KXELECT": "politics",
    "KXNBA": "sports", "KXNFL": "sports", "KXMLB": "sports",
    "KXNHL": "sports", "KXSOCCER": "sports", "KXNCAAMB": "sports",
    "KXFIRSTSUPERBOWLSONG": "entertainment", "KXSUPERBOWL": "entertainment",
    "KXOSCARS": "entertainment", "KXGRAMMYS": "entertainment", "KXEMMYS": "entertainment",
}
markets_df["category"] = markets_df["series_ticker"].map(CATEGORY_MAP).fillna("other")

print(f"Markets: {len(markets_df):,} | Candle rows: {len(candles_df):,}")
```

### "Price at open" definition
The opening price for a market = the `close_cents` of its **first candle** (earliest `period_end_ts` row in `candles_df` for that ticker). To compute: `candles_df.sort_values('period_end_ts').groupby('ticker').first()['close_cents']`.

### End each notebook with a Key Findings cell (markdown)
After each analysis, add a markdown cell summarising what was found. Example:
```markdown
## Key Findings
- YES bias: mean price across all market-days = 54¢ (> 50¢); YES markets settle YES 58% of the time
- Round-number anchoring: clear spikes at 25, 50, 75 in price histogram
- Sports markets: more momentum (positive lag-1 autocorrelation) vs crypto markets
→ Features to prioritise: dist_from_50, is_above_50, price_momentum, is_sports
```

### `01_data_overview.ipynb`
- Market count by series_ticker and result (yes/no/scalar)
- YES settlement rate (% resolving YES) by category
- Market duration distribution (close_time − open_time in days)
- Price at open vs. settlement outcome (scatter)
- Volume distribution across markets (log-scale histogram)

### `02_behavioral_patterns.ipynb`

Hypotheses to test:

| Hypothesis | Test |
|-----------|------|
| **Yes-bias** | Are prices systematically > 50¢? Is YES settlement rate > 50%? Reliability diagram. |
| **Calibration by category** | Bin prices into 5¢ buckets. Plot actual YES rate vs bin midpoint. Who is overconfident? |
| **Round-number anchoring** | Frequency histogram — peaks at 25, 50, 75, 99 vs adjacent values? |
| **Home-team proxy** | For KXNBA/KXNFL, does opening price correlate more with outcome than for KXBTC? |
| **Volume timing** | Normalise each market's timeline to [0,1]. When does trading peak? |

### `03_price_dynamics.ipynb`

| Question | Analysis |
|---------|---------|
| **Late-resolution drift** | Average price trajectory in final 7 days (aligned to settlement date). Converges toward 0 or 100? |
| **Mean reversion** | Daily return autocorrelation at lag 1, 2, 3 days |
| **Momentum** | Correlation between day D return and day D+1 return, by category |
| **Spread over time** | Normalised timeline [0,1] vs bid-ask spread. Narrows near settlement? |
| **Feature-label heatmap** | Pearson correlations of candidate features vs next_day_price |

---

## Task 13: FeatureEngineer — (ticker, day) Feature Matrix

**File**: `ml/feature_engineer.py`
**Status**: ⏳ Pending

### Feature design

Each row = one candle day for one market. Label = `close_cents` on the *next* calendar day (per-ticker shift by 1). Last candle row per market has no label and is dropped.

| Group | Feature columns |
|-------|----------------|
| Price | `close_cents`, `price_1d_change`, `price_7d_change`, `dist_from_50`, `is_above_50`, `price_ma7`, `price_momentum` (close − ma7) |
| Volume | `volume`, `volume_7d_avg`, `volume_spike` (volume ÷ volume_7d_avg), `cumulative_volume` |
| Spread | `bid_ask_spread` (yes_ask − yes_bid), `spread_1d_change` |
| Time | `days_to_close`, `days_since_open`, `market_duration_days`, `day_of_week` |
| Category | `is_crypto`, `is_financial`, `is_politics`, `is_sports`, `is_entertainment` |

### Class

```python
class FeatureEngineer:
    CATEGORY_MAP: dict[str, str]  # series_ticker → category string

    def __init__(self, store: DataStore = None) -> None

    def build_feature_matrix(
        self,
        min_market_days: int = 5,
    ) -> tuple[pd.DataFrame, pd.Series]
    # Returns (features_df, labels_series).
    # features_df also contains 'close_time' column for train/test split.
    # Drops: last candle row per market (no label); markets with < min_market_days candles.

    def build_live_features(
        self,
        markets: list[dict],
        candles_by_ticker: dict[str, list[dict]],
    ) -> pd.DataFrame
    # Used at inference time by MarketScorer. Same features, no label column.

    def _compute_rolling_features(self, df: pd.DataFrame) -> pd.DataFrame
    # Per-ticker groupby: moving averages, daily changes, cumulative volume.

    def _add_category_dummies(self, df: pd.DataFrame) -> pd.DataFrame
    # Maps series_ticker → category via CATEGORY_MAP; adds boolean columns.
```

### Implementation notes

**`CATEGORY_MAP`** (define as class constant):
```python
CATEGORY_MAP = {
    "KXBTC": "crypto", "KXETH": "crypto",
    "INXD": "financial", "KXFED": "financial", "KXCPI": "financial",
    "KXGDP": "financial", "KXJOBS": "financial", "KXRATE": "financial",
    "PRES": "politics", "KXELECT": "politics",
    "KXNBA": "sports", "KXNFL": "sports", "KXMLB": "sports",
    "KXNHL": "sports", "KXSOCCER": "sports", "KXNCAAMB": "sports",
    "KXFIRSTSUPERBOWLSONG": "entertainment", "KXSUPERBOWL": "entertainment",
    "KXOSCARS": "entertainment", "KXGRAMMYS": "entertainment", "KXEMMYS": "entertainment",
}
```

**`FEATURE_COLUMNS`** (define as module-level constant — used by ModelTrainer and MarketScorer to guarantee column order):
```python
FEATURE_COLUMNS = [
    "close_cents", "price_1d_change", "price_7d_change",
    "dist_from_50", "is_above_50", "price_ma7", "price_momentum",
    "volume", "volume_7d_avg", "volume_spike", "cumulative_volume",
    "bid_ask_spread", "spread_1d_change",
    "days_to_close", "days_since_open", "market_duration_days", "day_of_week",
    "is_crypto", "is_financial", "is_politics", "is_sports", "is_entertainment",
]
```

**Data join**: `build_feature_matrix` loads candles + markets from `store`, merges on `ticker` to attach `close_time`, `series_ticker`, `open_time`, `market_duration_days` to each candle row. Use `pd.merge(candles_df, markets_df[['ticker','close_time','series_ticker','open_time']], on='ticker', how='left')`.

**NaN handling for short series**: Rolling features on markets with < 7 days of history will produce NaNs.
- `price_7d_change`, `price_ma7`, `price_momentum`: fill NaN with 0 (no observed change)
- `volume_7d_avg`, `volume_spike`: fill NaN with column-wide median
- `spread_1d_change`: fill NaN with 0

**Label construction**: Sort each market's candles by `period_end_ts`, then `shift(-1)` the `close_cents` column within each ticker group. The last row has `NaN` label — drop it.

**`close_time` column in output**: Include in the DataFrame returned by `build_feature_matrix` but **exclude from `FEATURE_COLUMNS`**. Used by `ModelTrainer` to determine train/test split. Drop it before calling `model.fit()`.

### Train/test split (done in ModelTrainer, not here)
Sort by market `close_time`; take earliest 80% of unique markets as train set. No candle row from a test market may appear in training — prevents data leakage even when the same market has many candle rows.

### Tests (`tests/test_feature_engineer.py`)
~20 tests mocking `DataStore`:
- Rolling features computed correctly (7-day MA, momentum, cumulative volume)
- Last candle row per market excluded from labels
- Markets with fewer than `min_market_days` candles excluded
- Category dummies correct for each of the 5 categories
- `build_live_features` produces same columns (minus label)
- `close_time` column present in output for downstream splitting

---

## Task 14: ModelTrainer — XGBoost with Time-Based Split

**File**: `ml/model_trainer.py`
**Status**: ⏳ Pending

### Class

```python
@dataclass
class TrainedModel:
    model: Any                        # XGBRegressor instance
    feature_names: list[str]
    train_cutoff_date: str            # ISO8601: last close_time in train set
    train_metrics: dict[str, float]   # mae, rmse, r2, directional_accuracy
    test_metrics: dict[str, float]
    feature_importances: dict[str, float]  # {feature_name: importance_score}

DEFAULT_PARAMS = {
    "n_estimators": 500,
    "max_depth": 5,
    "learning_rate": 0.05,
    "subsample": 0.8,
    "colsample_bytree": 0.8,
    "min_child_weight": 10,
    "reg_lambda": 1.0,
    "objective": "reg:squarederror",
    "random_state": 42,
    "n_jobs": -1,
}

class ModelTrainer:
    MODEL_PATH = "models/gb_model.pkl"

    def __init__(self) -> None

    def train(
        self,
        features: pd.DataFrame,
        labels: pd.Series,
        market_close_dates: pd.Series,  # aligned; one date per feature row
        test_fraction: float = 0.2,
        params: dict = None,
    ) -> TrainedModel
    # 1. Sort unique close_dates; find 80th-percentile date = cutoff.
    # 2. Train rows: market close_time <= cutoff.
    #    Test rows:  market close_time > cutoff.
    # 3. Fit XGBRegressor on train split.
    # 4. Compute metrics on both splits.

    def save(self, model: TrainedModel, path: str = MODEL_PATH) -> None  # joblib.dump
    def load(self, path: str = MODEL_PATH) -> TrainedModel               # joblib.load

    def _compute_metrics(
        self,
        y_true: np.ndarray,
        y_pred: np.ndarray,
    ) -> dict[str, float]
    # Returns: {mae, rmse, r2, directional_accuracy}
    # directional_accuracy = fraction where sign(pred_change) == sign(true_change)
```

`ModelTrainingError` inherits from `Exception`.

### Implementation notes

**Imports**: `from xgboost import XGBRegressor`. If not installed, `ImportError` propagates naturally — the user will see `pip install -r requirements_ml.txt`.

**`directional_accuracy` computation**: Requires the current day's price to compute direction. Update `_compute_metrics` to accept `current_prices: np.ndarray` as a third argument:
```python
def _compute_metrics(self, y_true, y_pred, current_prices) -> dict[str, float]:
    true_direction = np.sign(y_true - current_prices)
    pred_direction = np.sign(y_pred - current_prices)
    directional_accuracy = np.mean(true_direction == pred_direction)
    ...
```
The `current_prices` array is `features["close_cents"].values` (the current-day close, before the label shift). Pass this from `train()` when calling `_compute_metrics`.

**Train/test split implementation**:
```python
unique_dates = sorted(market_close_dates.unique())
cutoff_idx = int(len(unique_dates) * (1 - test_fraction))
cutoff_date = unique_dates[cutoff_idx]
train_mask = market_close_dates <= cutoff_date
test_mask  = market_close_dates > cutoff_date
X_train, X_test = features[FEATURE_COLUMNS][train_mask], features[FEATURE_COLUMNS][test_mask]
y_train, y_test = labels[train_mask], labels[test_mask]
current_train = features["close_cents"][train_mask]
current_test  = features["close_cents"][test_mask]
```

**Feature columns**: Call `model.fit(X_train[FEATURE_COLUMNS], y_train)`. Import `FEATURE_COLUMNS` from `ml.feature_engineer`.

### Tests (`tests/test_model_trainer.py`)
~15 tests (mock XGBRegressor where needed, use small synthetic DataFrames):
- Time-based split at correct date cutoff
- No test market rows appear in training data
- Metrics computed correctly (MAE, RMSE, R², directional accuracy)
- `save`/`load` round-trip preserves feature_names and metrics
- `params` argument overrides defaults

---

## Task 15: ModelEvaluator — Metrics + By-Category Report

**File**: `ml/model_evaluator.py`
**Status**: ⏳ Pending

### Class

```python
@dataclass
class EvaluationReport:
    overall: dict[str, float]         # mae, rmse, r2, directional_accuracy
    by_category: dict[str, dict]      # same keys, per category label
    feature_importances: list[tuple]  # [(name, importance), ...] sorted descending
    n_test_rows: int
    train_cutoff_date: str

class ModelEvaluator:
    def __init__(self, model: TrainedModel) -> None

    def evaluate(
        self,
        features: pd.DataFrame,
        labels: pd.Series,
    ) -> EvaluationReport
    # Computes overall metrics + breaks down by category column.
    # Category determined from is_crypto / is_sports / etc. dummy columns.

    def display_report(self, report: EvaluationReport) -> None
    # Prints to stdout:
    #   — Overall metrics table
    #   — By-category metrics table
    #   — Top-10 feature importances
```

### Implementation notes

**Passing features to model**: Filter to `model.feature_names` before calling predict:
```python
X = features[model.feature_names].values
y_pred = model.model.predict(X)
```

**Category inference from dummy columns**: Each row should have exactly one `is_*` column set to `True`. Determine category per row:
```python
category_cols = ["is_crypto", "is_financial", "is_politics", "is_sports", "is_entertainment"]
features["_category"] = features[category_cols].idxmax(axis=1).str.replace("is_", "")
# If all dummy cols are 0, idxmax returns the first col — add a guard:
features.loc[features[category_cols].sum(axis=1) == 0, "_category"] = "unknown"
```

**`directional_accuracy` in evaluate**: Needs `close_cents` from features. Use `features["close_cents"]` as the current-price reference, just as in ModelTrainer.

**Display format** (exact stdout shape):
```
=== Model Evaluation Report ===
Train cutoff: 2025-09-15  |  Test rows: 12,345

--- Overall Metrics ---
MAE:                   8.2¢
RMSE:                 12.1¢
R²:                    0.42
Directional accuracy: 61.3%

--- By Category ---
Category       MAE    RMSE    R²   Dir%
crypto         6.1    9.8    0.51  64%
financial      7.4   11.2    0.45  62%
politics      10.3   15.1    0.31  57%
sports         8.9   13.4    0.38  60%
entertainment 11.2   16.8    0.22  55%

--- Top 10 Feature Importances ---
1. days_to_close        0.182
2. close_cents          0.141
...
```

### Tests (`tests/test_model_evaluator.py`)
~10 tests (mock `TrainedModel.model.predict`):
- Overall MAE/RMSE/R² computed correctly from known inputs
- `directional_accuracy` correct: test with known y_true, y_pred, current_prices
- By-category breakdown produces one dict entry per category present in features
- Feature importances sorted descending
- `display_report` prints "Overall" and "Category" sections to stdout

---

## Task 16: MarketScorer — Score Active Markets, Generate Recommendations

**File**: `ml/market_scorer.py`
**Status**: ⏳ Pending

### Class

```python
@dataclass
class Recommendation:
    ticker: str
    title: str
    current_price_cents: int
    predicted_price_cents: int
    edge_cents: int               # predicted − current; positive = buy YES
    recommended_side: str         # "yes" if edge > 0 else "no"
    days_to_close: int
    volume_24h: int
    series_ticker: str

class MarketScorer:
    def __init__(
        self,
        model: TrainedModel,
        client: KalshiClient = None,
        store: DataStore = None,
    ) -> None

    def fetch_active_markets(
        self,
        series_tickers: list[str] = None,
    ) -> list[dict]
    # Uses client.get_markets(status="open", series_ticker=...).
    # Iterates POPULAR_SERIES when series_tickers not provided.

    def fetch_recent_candles(
        self,
        tickers: list[str],
        days: int = 30,
    ) -> dict[str, list[dict]]
    # Batch candlestick fetch (live endpoint only, markets are active).
    # Returns {ticker: [candle, ...]}

    def score(
        self,
        markets: list[dict],
        candles_by_ticker: dict[str, list[dict]],
    ) -> list[Recommendation]
    # 1. Builds features via FeatureEngineer.build_live_features().
    # 2. Runs model.predict() on feature matrix.
    # 3. Constructs Recommendation per market.
    # 4. Returns sorted by abs(edge_cents) descending.

    def get_recommendations(
        self,
        min_edge_cents: int = 5,
        max_days_to_close: int = 30,
        top_n: int = 20,
    ) -> list[Recommendation]
    # Orchestrates: fetch_active_markets → fetch_recent_candles → score → filter.

    def display_recommendations(
        self,
        recommendations: list[Recommendation],
    ) -> None
    # Formatted table to stdout:
    # Ticker | Title (truncated) | Current | Predicted | Edge | Side | Days Left
```

`ScoringError` inherits from `Exception`.

### Implementation notes

**`FeatureEngineer` instantiation**: Create internally in `__init__`:
```python
self.engineer = FeatureEngineer(store=store)
```

**`current_price_cents` source**: The latest (most recent) candle for each market = last element of `candles_by_ticker[ticker]` sorted by `period_end_ts`. Use its `close_cents`.

**`days_to_close` computation**:
```python
from datetime import datetime, timezone
close_dt = pd.to_datetime(market["close_time"])
today = datetime.now(timezone.utc)
days_to_close = max(0, (close_dt - today).days)
```

**`volume_24h` source**: Use the `volume_24h` field from the active market dict returned by `client.get_markets()`. This is a contract count (not a dollar amount).

**Empty candles handling**: If `candles_by_ticker.get(ticker, [])` is empty (market just opened, no candle history), skip that ticker from scoring. Log a debug message. Do not raise an error.

**Batch chunking for `fetch_recent_candles`**: `get_batch_candlesticks` accepts max 100 tickers. Chunk:
```python
for i in range(0, len(tickers), 100):
    batch = tickers[i:i+100]
    result = self.client.get_batch_candlesticks(batch, ...)
    for ticker, candles in result.get("candlesticks", {}).items():
        candles_by_ticker[ticker] = candles
```

**Feature building**: Call `self.engineer.build_live_features(markets, candles_by_ticker)`. This returns a DataFrame with `FEATURE_COLUMNS` + a `ticker` column. Run `model.model.predict(df[model.feature_names])` and align predictions back to tickers via the `ticker` column.

**Recommended side**:
- `edge_cents > 0` → buy YES (predicted to rise)
- `edge_cents < 0` → edge_cents is negative; recommend buying NO at `100 - current_price_cents`; set `recommended_side = "no"`, `edge_cents = abs(edge_cents)`

### Tests (`tests/test_market_scorer.py`)
~15 tests mocking `KalshiClient` and `TrainedModel`:
- `fetch_active_markets` iterates all series tickers when none provided
- `score` assigns "yes" when edge > 0, "no" when edge < 0
- `score` sorts by abs(edge_cents) descending
- `get_recommendations` filters by min_edge_cents
- `get_recommendations` filters by max_days_to_close
- `display_recommendations` prints header row + data rows to stdout
- `KalshiAPIError` in `fetch_active_markets` raises `ScoringError`

---

## Task 17: MLPipeline CLI

**File**: `ml/ml_pipeline.py`
**Status**: ⏳ Pending

### Commands

```bash
python3 ml/ml_pipeline.py collect     # Task 11: pull historical data (~30–60 min)
python3 ml/ml_pipeline.py train       # Tasks 13+14: feature engineering + model fit
python3 ml/ml_pipeline.py evaluate    # Task 15: print evaluation report
python3 ml/ml_pipeline.py recommend   # Task 16: score active markets + print recs
python3 ml/ml_pipeline.py all         # collect → train → evaluate (no EDA step)
```

Uses `argparse`. Each subcommand initialises only the dependencies it needs. Prints step name, progress, and elapsed time. `ConfigurationError` on startup → clean error message + exit.

### Implementation notes

**`sys.path` setup** (top of `ml_pipeline.py`):
```python
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))  # adds project root to path
```
This ensures `from data.data_store import DataStore` and `from kalshi_client import KalshiClient` resolve correctly when running `python3 ml/ml_pipeline.py`.

**Subcommand sequences** (exact module instantiation order):

`collect`:
```python
client = KalshiClient()
store = DataStore()
collector = DataCollector(client=client, store=store)
summary = collector.run()
print(summary)
```

`train`:
```python
store = DataStore()
engineer = FeatureEngineer(store=store)
features, labels = engineer.build_feature_matrix()
close_dates = features["close_time"]
trainer = ModelTrainer()
model = trainer.train(features, labels, close_dates)
trainer.save(model)
print(f"Train MAE: {model.train_metrics['mae']:.1f}¢  Test MAE: {model.test_metrics['mae']:.1f}¢")
```

`evaluate`:
```python
trainer = ModelTrainer()
model = trainer.load()
store = DataStore()
engineer = FeatureEngineer(store=store)
features, labels = engineer.build_feature_matrix()
# Only evaluate on test rows (dates after train_cutoff_date)
test_mask = pd.to_datetime(features["close_time"]) > pd.to_datetime(model.train_cutoff_date)
evaluator = ModelEvaluator(model=model)
report = evaluator.evaluate(features[test_mask], labels[test_mask])
evaluator.display_report(report)
```

`recommend`:
```python
trainer = ModelTrainer()
model = trainer.load()
client = KalshiClient()
store = DataStore()
scorer = MarketScorer(model=model, client=client, store=store)
recs = scorer.get_recommendations()
scorer.display_recommendations(recs)
```

`all`: runs `collect` → `train` → `evaluate` in sequence. Does not run EDA.

**Elapsed time display**: Wrap each subcommand in:
```python
import time
start = time.time()
# ... run subcommand ...
print(f"\nCompleted in {time.time() - start:.1f}s")
```

### Tests (`tests/test_ml_pipeline.py`)
~5 tests (mock all modules): each subcommand calls the expected module methods; `all` calls the correct sequence; `ConfigurationError` from `KalshiClient()` prints error and exits with code 1 without raising.

---

## Verification

After all tasks complete:

```bash
# All 275 + new tests pass
python3 -m pytest tests/ -m "not integration" -v

# End-to-end pipeline
python3 ml/ml_pipeline.py collect     # populates data_store/
python3 ml/ml_pipeline.py train       # prints train/test metrics
python3 ml/ml_pipeline.py evaluate    # prints evaluation report
python3 ml/ml_pipeline.py recommend   # prints recommendation table

# EDA (run after collect)
cd eda && jupyter notebook
```

**Expected model baseline**: test MAE < 10 cents (random baseline ≈ 25 cents).

---

## Implementation Sequence

1. **Task 9** — KalshiClient extensions + tests (foundation for everything)
2. **Task 10** — DataStore + tests
3. **Task 11** — DataCollector + tests
4. **Run collect** — `python3 ml/ml_pipeline.py collect` to populate database
5. **Task 12** — EDA notebooks (explore actual collected data; informs feature choices)
6. **Task 13** — FeatureEngineer + tests (informed by EDA findings)
7. **Task 14** — ModelTrainer + tests
8. **Task 15** — ModelEvaluator + tests
9. **Task 16** — MarketScorer + tests
10. **Task 17** — MLPipeline CLI + end-to-end run
