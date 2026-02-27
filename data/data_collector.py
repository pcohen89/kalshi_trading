"""
DataCollector — market and candlestick ingestion (Task 11).

Orchestrates the full data pull across live and historical Kalshi API endpoints.
Routes each market to the correct candlestick endpoint based on settlement age,
with checkpointing to skip already-collected tickers.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Optional

import pandas as pd

from kalshi_client import KalshiClient, KalshiAPIError
from data.data_store import DataStore
from trade_executor import TradeExecutor as _TradeExecutor

# Module-level alias so the rest of the code reads clearly
POPULAR_SERIES = _TradeExecutor.POPULAR_SERIES

logger = logging.getLogger(__name__)


class DataCollectionError(Exception):
    """Raised for unrecoverable data collection failures."""


@dataclass
class CollectionSummary:
    """Result of a full collection run."""
    markets_found: int = 0
    markets_new: int = 0
    tickers_with_candles: int = 0
    candles_collected: int = 0
    errors: list = field(default_factory=list)

    def __str__(self) -> str:
        error_str = f"{len(self.errors)} tickers skipped" if self.errors else "0 errors"
        return (
            f"[collect] Done. "
            f"Markets: {self.markets_found:,} total ({self.markets_new:,} new). "
            f"Candles: {self.candles_collected:,} rows. "
            f"Errors: {error_str}."
        )


class DataCollector:
    """Orchestrates full data collection from Kalshi live + historical APIs."""

    BATCH_SIZE = 100  # max tickers per batch candlestick call
    MAX_PAGES = 50    # safety limit for pagination

    def __init__(
        self,
        client: Optional[KalshiClient] = None,
        store: Optional[DataStore] = None,
    ) -> None:
        self.client = client or KalshiClient()
        self.store = store or DataStore()
        self._cutoff_ts: Optional[int] = None  # cached after first call

    # -------------------------------------------------------------------------
    # Public API
    # -------------------------------------------------------------------------

    def get_cutoff_ts(self) -> int:
        """Return the live/historical boundary (epoch seconds). Cached after first call."""
        if self._cutoff_ts is None:
            result = self.client.get_historical_cutoff()
            self._cutoff_ts = result["live_cutoff_ts"]
        return self._cutoff_ts

    def collect_settled_markets(
        self,
        series_tickers: Optional[list] = None,
        days_back: int = 180,
    ) -> tuple:
        """Fetch settled markets from both live and historical endpoints.

        Queries GET /markets?status=settled and GET /historical/markets for
        each series ticker (or all POPULAR_SERIES if series_tickers is None).
        Filters to markets whose close_time is within the last days_back days,
        saves to store, and returns (markets_list, new_count).
        """
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=days_back)
        all_markets: dict = {}  # ticker → market dict (deduplicates across endpoints)

        if series_tickers is None:
            series_tickers = list(POPULAR_SERIES)

        for series in series_tickers:
            logger.info("[collect] Series %s: fetching live settled markets", series)
            live = self._paginate_markets(series_ticker=series, status="settled")
            for m in live:
                all_markets[m["ticker"]] = m

            logger.info("[collect] Series %s: fetching historical markets", series)
            historical = self._paginate_historical_markets(series_ticker=series)
            for m in historical:
                all_markets[m["ticker"]] = m

        filtered = [m for m in all_markets.values() if _within_window(m, cutoff_date)]
        new_count = self.store.save_markets(filtered) if filtered else 0

        logger.info("[collect] %d markets found (%d new)", len(filtered), new_count)
        return filtered, new_count

    def collect_candlesticks(
        self,
        tickers: list,
        granularity: int = 1440,
        days_back: int = 180,
    ) -> dict:
        """Collect candlesticks for the given tickers.

        Skips tickers already present in the store (checkpointing). Splits
        remaining tickers into live (batch endpoint) and historical (per-ticker
        endpoint) based on settlement_ts; falls back to close_time when
        settlement_ts is absent. Continues past individual ticker errors.

        Returns {ticker: candle_count}.
        """
        already_collected = self.store.get_collected_tickers()
        remaining = [t for t in tickers if t not in already_collected]

        if not remaining:
            logger.info("[collect] All %d tickers already collected — skipping.", len(tickers))
            return {}

        cutoff_ts = self.get_cutoff_ts()
        end_ts = int(datetime.now(timezone.utc).timestamp())
        start_ts = int((datetime.now(timezone.utc) - timedelta(days=days_back)).timestamp())

        # Build epoch-seconds lookup: prefer settlement_ts, fall back to close_time.
        # Markets without settlement_ts are open/pending — close_time is the proxy.
        ticker_to_epoch: dict = {}
        markets_df = self.store.get_markets()
        if not markets_df.empty:
            settlement_col = markets_df["settlement_ts"].fillna("").astype(str)
            close_time_col = markets_df["close_time"].fillna("").astype(str)
            for ticker, s_ts, c_time in zip(markets_df["ticker"], settlement_col, close_time_col):
                ticker_to_epoch[ticker] = _parse_ts(s_ts or c_time)

        live_tickers = []
        historical_tickers = []
        for ticker in remaining:
            epoch = ticker_to_epoch.get(ticker)
            if epoch is not None and epoch <= cutoff_ts:
                historical_tickers.append(ticker)
            else:
                live_tickers.append(ticker)

        total = len(remaining)
        live_done = 0
        hist_done = 0

        print(
            f"[collect] Fetching candles for {total} tickers "
            f"({len(live_tickers)} live batch, {len(historical_tickers)} historical per-ticker)"
        )

        results: dict = {}

        # Batch-fetch live tickers (up to BATCH_SIZE per API call)
        for i in range(0, len(live_tickers), self.BATCH_SIZE):
            batch = live_tickers[i:i + self.BATCH_SIZE]
            try:
                resp = self.client.get_batch_candlesticks(
                    batch, period_interval=granularity, start_ts=start_ts, end_ts=end_ts
                )
                candles_by_ticker = resp.get("candlesticks", {})
                for ticker, candles in candles_by_ticker.items():
                    results[ticker] = self.store.save_candles(ticker, candles, granularity)
            except KalshiAPIError as e:
                logger.error("[collect] Batch candlestick error: %s", e)
                for ticker in batch:
                    results[ticker] = 0
            live_done += len(batch)
            print(
                f"[collect] Fetching candles: {live_done + hist_done}/{total} done "
                f"({live_done} live batch, {hist_done} historical per-ticker)"
            )

        # Per-ticker fetch for historical tickers
        for ticker in historical_tickers:
            try:
                resp = self.client.get_market_candlesticks(
                    ticker,
                    period_interval=granularity,
                    start_ts=start_ts,
                    end_ts=end_ts,
                    historical=True,
                )
                candles = resp.get("candlesticks", [])
                results[ticker] = self.store.save_candles(ticker, candles, granularity)
            except KalshiAPIError as e:
                logger.error("[collect] Ticker %s candlestick error: %s", ticker, e)
                results[ticker] = 0
            hist_done += 1
            # Print after every BATCH_SIZE historical tickers and at the final one
            if hist_done % self.BATCH_SIZE == 0 or hist_done == len(historical_tickers):
                print(
                    f"[collect] Fetching candles: {live_done + hist_done}/{total} done "
                    f"({live_done} live batch, {hist_done} historical per-ticker)"
                )

        return results

    def run(
        self,
        series_tickers: Optional[list] = None,
        days_back: int = 180,
    ) -> CollectionSummary:
        """Full orchestration: markets → candles → return summary.

        series_tickers defaults to POPULAR_SERIES from trade_executor.
        """
        summary = CollectionSummary()

        markets, markets_new = self.collect_settled_markets(
            series_tickers=series_tickers, days_back=days_back
        )
        summary.markets_found = len(markets)
        summary.markets_new = markets_new

        if markets:
            tickers = [m["ticker"] for m in markets]
            candle_results = self.collect_candlesticks(tickers, days_back=days_back)
            summary.tickers_with_candles = sum(1 for c in candle_results.values() if c > 0)
            summary.candles_collected = sum(candle_results.values())

        print(str(summary))
        return summary

    # -------------------------------------------------------------------------
    # Private pagination helpers
    # -------------------------------------------------------------------------

    def _paginate_markets(self, series_ticker: str, status: str) -> list:
        """Paginate GET /markets for a single series/status combination."""
        results = []
        cursor = None
        for _ in range(self.MAX_PAGES):
            resp = self.client.get_markets(
                limit=1000,
                cursor=cursor,
                series_ticker=series_ticker,
                status=status,
            )
            page = resp.get("markets", [])
            results.extend(page)
            cursor = resp.get("cursor", "")
            if not cursor or not page:
                break
        return results

    def _paginate_historical_markets(self, series_ticker: str) -> list:
        """Paginate GET /historical/markets for a single series."""
        results = []
        cursor = None
        for _ in range(self.MAX_PAGES):
            resp = self.client.get_historical_markets(
                limit=1000,
                cursor=cursor,
                series_ticker=series_ticker,
            )
            page = resp.get("markets", [])
            results.extend(page)
            cursor = resp.get("cursor", "")
            if not cursor or not page:
                break
        return results


# ---------------------------------------------------------------------------
# Module-level helpers
# ---------------------------------------------------------------------------

def _within_window(market: dict, cutoff_date: datetime) -> bool:
    """Return True if the market's close_time falls within the collection window."""
    close_time_str = market.get("close_time", "")
    if not close_time_str:
        return False
    try:
        close_dt = pd.to_datetime(close_time_str, utc=True).to_pydatetime()
        return close_dt >= cutoff_date
    except Exception:
        return False


def _parse_ts(ts_str: str) -> Optional[int]:
    """Parse an ISO8601 timestamp string to epoch seconds. Returns None on failure."""
    if not ts_str:
        return None
    try:
        return int(pd.to_datetime(ts_str, utc=True).timestamp())
    except Exception:
        return None
