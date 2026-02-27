"""
DataStore — CSV persistence layer for the ML pipeline.

Provides upsert-based storage for Kalshi market metadata and OHLC candlestick
data. Two CSV files are maintained:
  - data_store/markets.csv  — one row per market, keyed on ticker
  - data_store/candles.csv  — one row per (ticker, period_end_ts, granularity)
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import pandas as pd

logger = logging.getLogger(__name__)


class DataStoreError(Exception):
    """Raised for DataStore I/O or data integrity failures."""


class DataStore:
    """CSV-backed persistence layer for market and candlestick data."""

    MARKETS_COLUMNS = [
        "ticker", "event_ticker", "series_ticker", "title", "market_type",
        "status", "result", "settlement_value_cents", "open_time", "close_time",
        "settlement_ts", "collected_at",
    ]
    CANDLES_COLUMNS = [
        "ticker", "period_end_ts", "granularity", "open_cents", "high_cents",
        "low_cents", "close_cents", "volume", "open_interest",
        "yes_bid_cents", "yes_ask_cents",
    ]

    def __init__(
        self,
        markets_path: str = "data_store/markets.csv",
        candles_path: str = "data_store/candles.csv",
    ) -> None:
        self.markets_path = markets_path
        self.candles_path = candles_path
        Path(self.markets_path).parent.mkdir(parents=True, exist_ok=True)
        Path(self.candles_path).parent.mkdir(parents=True, exist_ok=True)

    # -------------------------------------------------------------------------
    # Write methods
    # -------------------------------------------------------------------------

    def save_markets(self, markets: list[dict]) -> int:
        """Append markets to CSV; deduplicate on ticker (keep last).

        Returns count of tickers that were not already present before this call.
        """
        if not markets:
            return 0

        collected_at = datetime.now(timezone.utc).isoformat()
        new_rows = []
        for m in markets:
            settlement_dollars = m.get("settlement_value_dollars") or 0
            try:
                settlement_cents = round(float(settlement_dollars) * 100)
            except (TypeError, ValueError):
                logger.warning(
                    "Invalid settlement_value_dollars for ticker %s: %r — storing 0",
                    m.get("ticker"),
                    settlement_dollars,
                )
                settlement_cents = 0

            new_rows.append({
                "ticker": m.get("ticker", ""),
                "event_ticker": m.get("event_ticker", ""),
                "series_ticker": m.get("series_ticker", ""),
                "title": m.get("title", ""),
                "market_type": m.get("market_type", ""),
                "status": m.get("status", ""),
                "result": m.get("result", ""),
                "settlement_value_cents": settlement_cents,
                "open_time": m.get("open_time", ""),
                "close_time": m.get("close_time", ""),
                "settlement_ts": m.get("settlement_ts", ""),
                "collected_at": collected_at,
            })

        new_df = pd.DataFrame(new_rows, columns=self.MARKETS_COLUMNS)

        if Path(self.markets_path).exists():
            existing_df = pd.read_csv(self.markets_path)
            existing_tickers = set(existing_df["ticker"].tolist())
            combined = pd.concat([existing_df, new_df], ignore_index=True)
        else:
            existing_tickers = set()
            combined = new_df

        # Count unique new tickers (set handles duplicates within the same batch)
        newly_added = len({r["ticker"] for r in new_rows} - existing_tickers)

        combined = combined.drop_duplicates(subset=["ticker"], keep="last")
        combined.to_csv(self.markets_path, index=False)

        return newly_added

    def save_candles(self, ticker: str, candles: list[dict], granularity: int) -> int:
        """Append candles for a ticker; deduplicate on (ticker, period_end_ts, granularity).

        Returns count of (ticker, period_end_ts, granularity) rows not already present.
        """
        if not candles:
            return 0

        new_rows = []
        for c in candles:
            ts = c.get("end_period_ts")
            if not ts:
                logger.warning(
                    "Candle missing end_period_ts for ticker %s — skipping: %r", ticker, c
                )
                continue
            period_end_ts = datetime.fromtimestamp(ts, tz=timezone.utc).isoformat()
            price = c.get("price", {})
            yes_bid = c.get("yes_bid", {})
            yes_ask = c.get("yes_ask", {})
            new_rows.append({
                "ticker": ticker,
                "period_end_ts": period_end_ts,
                "granularity": granularity,
                "open_cents": price.get("open", 0),
                "high_cents": price.get("high", 0),
                "low_cents": price.get("low", 0),
                "close_cents": price.get("close", 0),
                "volume": c.get("volume", 0),
                "open_interest": c.get("open_interest", 0),
                "yes_bid_cents": yes_bid.get("close", 0),
                "yes_ask_cents": yes_ask.get("close", 0),
            })

        if not new_rows:
            return 0

        new_df = pd.DataFrame(new_rows, columns=self.CANDLES_COLUMNS)
        key_cols = ["ticker", "period_end_ts", "granularity"]

        if Path(self.candles_path).exists():
            existing_df = pd.read_csv(self.candles_path)
            existing_keys = set(
                zip(existing_df["ticker"], existing_df["period_end_ts"], existing_df["granularity"])
            )
            combined = pd.concat([existing_df, new_df], ignore_index=True)
        else:
            existing_keys = set()
            combined = new_df

        # Count unique new composite keys (set handles duplicates within the same batch)
        newly_added = len(
            {(r["ticker"], r["period_end_ts"], r["granularity"]) for r in new_rows} - existing_keys
        )

        combined = combined.drop_duplicates(subset=key_cols, keep="last")
        combined.to_csv(self.candles_path, index=False)

        return newly_added

    # -------------------------------------------------------------------------
    # Read methods
    # -------------------------------------------------------------------------

    def get_markets(
        self,
        series_ticker: Optional[str] = None,
        status: Optional[str] = None,
    ) -> pd.DataFrame:
        """Load markets CSV, optionally filtered by series_ticker and/or status."""
        if not Path(self.markets_path).exists():
            return pd.DataFrame(columns=self.MARKETS_COLUMNS)
        df = pd.read_csv(self.markets_path)
        if series_ticker:
            df = df[df["series_ticker"] == series_ticker]
        if status:
            df = df[df["status"] == status]
        return df.reset_index(drop=True)

    def get_candles(self, ticker: Optional[str] = None) -> pd.DataFrame:
        """Load candles CSV, optionally filtered by ticker."""
        if not Path(self.candles_path).exists():
            return pd.DataFrame(columns=self.CANDLES_COLUMNS)
        df = pd.read_csv(self.candles_path)
        if ticker:
            df = df[df["ticker"] == ticker]
        return df.reset_index(drop=True)

    def ticker_has_candles(self, ticker: str) -> bool:
        """Return True if the ticker has at least one candle stored."""
        if not Path(self.candles_path).exists():
            return False
        df = pd.read_csv(self.candles_path)
        return ticker in df["ticker"].values

    def get_collected_tickers(self) -> set:
        """Return set of tickers that already have candles (used for checkpointing)."""
        if not Path(self.candles_path).exists():
            return set()
        df = pd.read_csv(self.candles_path)
        return set(df["ticker"].unique())
