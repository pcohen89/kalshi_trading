"""Tests for data/data_collector.py (Task 11)."""

import os
import sys

import pytest
from unittest.mock import Mock, patch, call

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from kalshi_client import KalshiAPIError
from data.data_collector import DataCollector, CollectionSummary


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_client():
    return Mock()


@pytest.fixture
def mock_store():
    store = Mock()
    store.get_collected_tickers.return_value = set()
    store.get_markets.return_value = _empty_df()
    store.save_markets.return_value = 0
    store.save_candles.return_value = 0
    return store


@pytest.fixture
def collector(mock_client, mock_store):
    return DataCollector(client=mock_client, store=mock_store)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _empty_df():
    import pandas as pd
    from data.data_store import DataStore
    return pd.DataFrame(columns=DataStore.MARKETS_COLUMNS)


def _markets_df(tickers_and_ts: list):
    """Build a minimal markets DataFrame with ticker + settlement_ts columns."""
    import pandas as pd
    from data.data_store import DataStore
    rows = []
    for ticker, settlement_ts in tickers_and_ts:
        row = {col: "" for col in DataStore.MARKETS_COLUMNS}
        row["ticker"] = ticker
        row["settlement_ts"] = settlement_ts
        rows.append(row)
    return pd.DataFrame(rows, columns=DataStore.MARKETS_COLUMNS)


def _markets_df_with_close_time(tickers_info: list):
    """Build a markets DataFrame with ticker, settlement_ts, and close_time columns."""
    import pandas as pd
    from data.data_store import DataStore
    rows = []
    for ticker, settlement_ts, close_time in tickers_info:
        row = {col: "" for col in DataStore.MARKETS_COLUMNS}
        row["ticker"] = ticker
        row["settlement_ts"] = settlement_ts
        row["close_time"] = close_time
        rows.append(row)
    return pd.DataFrame(rows, columns=DataStore.MARKETS_COLUMNS)


def _market_dict(ticker="KXBTC-A", close_time="2025-06-01T00:00:00Z"):
    return {
        "ticker": ticker,
        "series_ticker": "KXBTC",
        "close_time": close_time,
        "settlement_ts": "2025-06-01T12:00:00Z",
        "settlement_value_dollars": 1.0,
    }


def _candle(ts=1000):
    return {
        "end_period_ts": ts,
        "price": {"open": 40, "high": 50, "low": 35, "close": 45},
        "yes_bid": {"close": 44},
        "yes_ask": {"close": 46},
        "volume": 100,
        "open_interest": 200,
    }


# ---------------------------------------------------------------------------
# get_cutoff_ts
# ---------------------------------------------------------------------------

class TestGetCutoffTs:
    def test_returns_live_cutoff_ts(self, collector, mock_client):
        mock_client.get_historical_cutoff.return_value = {
            "live_cutoff_ts": 9999,
            "historical_cutoff_ts": 8888,
        }
        assert collector.get_cutoff_ts() == 9999

    def test_caches_result_only_one_api_call(self, collector, mock_client):
        mock_client.get_historical_cutoff.return_value = {
            "live_cutoff_ts": 9999,
            "historical_cutoff_ts": 8888,
        }
        collector.get_cutoff_ts()
        collector.get_cutoff_ts()
        mock_client.get_historical_cutoff.assert_called_once()


# ---------------------------------------------------------------------------
# collect_settled_markets
# ---------------------------------------------------------------------------

class TestCollectSettledMarkets:
    def test_calls_both_live_and_historical_per_series(self, collector, mock_client, mock_store):
        mock_client.get_markets.return_value = {"markets": [], "cursor": ""}
        mock_client.get_historical_markets.return_value = {"markets": [], "cursor": ""}

        collector.collect_settled_markets(series_tickers=["KXBTC"])

        mock_client.get_markets.assert_called_once()
        mock_client.get_historical_markets.assert_called_once()

    def test_deduplicates_markets_across_endpoints(self, collector, mock_client, mock_store):
        dup = _market_dict("KXBTC-A", close_time="2025-12-01T00:00:00Z")
        mock_client.get_markets.return_value = {"markets": [dup], "cursor": ""}
        mock_client.get_historical_markets.return_value = {"markets": [dup], "cursor": ""}

        result, _ = collector.collect_settled_markets(series_tickers=["KXBTC"])
        assert len(result) == 1

    def test_filters_markets_outside_days_back_window(self, collector, mock_client, mock_store):
        old_market = _market_dict("KXBTC-OLD", close_time="2020-01-01T00:00:00Z")
        recent_market = _market_dict("KXBTC-NEW", close_time="2025-12-01T00:00:00Z")
        mock_client.get_markets.return_value = {
            "markets": [old_market, recent_market],
            "cursor": "",
        }
        mock_client.get_historical_markets.return_value = {"markets": [], "cursor": ""}

        result, _ = collector.collect_settled_markets(series_tickers=["KXBTC"], days_back=180)
        tickers = [m["ticker"] for m in result]
        assert "KXBTC-OLD" not in tickers
        assert "KXBTC-NEW" in tickers

    def test_saves_filtered_markets_to_store(self, collector, mock_client, mock_store):
        mock_client.get_markets.return_value = {
            "markets": [_market_dict("KXBTC-A", close_time="2025-12-01T00:00:00Z")],
            "cursor": "",
        }
        mock_client.get_historical_markets.return_value = {"markets": [], "cursor": ""}

        collector.collect_settled_markets(series_tickers=["KXBTC"], days_back=180)
        mock_store.save_markets.assert_called_once()

    def test_returns_new_count_from_save_markets(self, collector, mock_client, mock_store):
        mock_client.get_markets.return_value = {
            "markets": [_market_dict("KXBTC-A", close_time="2025-12-01T00:00:00Z")],
            "cursor": "",
        }
        mock_client.get_historical_markets.return_value = {"markets": [], "cursor": ""}
        mock_store.save_markets.return_value = 1

        _, new_count = collector.collect_settled_markets(series_tickers=["KXBTC"], days_back=180)
        assert new_count == 1

    def test_empty_response_returns_empty_list(self, collector, mock_client, mock_store):
        mock_client.get_markets.return_value = {"markets": [], "cursor": ""}
        mock_client.get_historical_markets.return_value = {"markets": [], "cursor": ""}

        result, new_count = collector.collect_settled_markets(series_tickers=["KXBTC"])
        assert result == []
        assert new_count == 0
        mock_store.save_markets.assert_not_called()


# ---------------------------------------------------------------------------
# collect_candlesticks
# ---------------------------------------------------------------------------

class TestCollectCandlesticks:
    def test_skips_tickers_already_in_store(self, collector, mock_client, mock_store):
        mock_store.get_collected_tickers.return_value = {"KXBTC-A", "KXBTC-B"}
        mock_client.get_historical_cutoff.return_value = {"live_cutoff_ts": 9999}

        result = collector.collect_candlesticks(["KXBTC-A", "KXBTC-B"])
        assert result == {}
        mock_client.get_batch_candlesticks.assert_not_called()
        mock_client.get_market_candlesticks.assert_not_called()

    def test_routes_live_tickers_to_batch_endpoint(self, collector, mock_client, mock_store):
        # settlement_ts is well in the future → live endpoint
        mock_store.get_markets.return_value = _markets_df([
            ("KXBTC-A", "2099-01-01T00:00:00Z"),
        ])
        mock_client.get_historical_cutoff.return_value = {"live_cutoff_ts": 1000}
        mock_client.get_batch_candlesticks.return_value = {
            "candlesticks": {"KXBTC-A": [_candle()]}
        }

        collector.collect_candlesticks(["KXBTC-A"])
        mock_client.get_batch_candlesticks.assert_called_once()
        mock_client.get_market_candlesticks.assert_not_called()

    def test_routes_historical_tickers_to_per_ticker_endpoint(self, collector, mock_client, mock_store):
        # settlement_ts is in 2020 → historical endpoint (assuming cutoff > 2020)
        mock_store.get_markets.return_value = _markets_df([
            ("KXBTC-A", "2020-01-01T00:00:00Z"),
        ])
        # cutoff is set well into the future so 2020 is definitely historical
        future_cutoff = int(__import__("datetime").datetime(2099, 1, 1).timestamp())
        mock_client.get_historical_cutoff.return_value = {"live_cutoff_ts": future_cutoff}
        mock_client.get_market_candlesticks.return_value = {"candlesticks": [_candle()]}

        collector.collect_candlesticks(["KXBTC-A"])
        mock_client.get_market_candlesticks.assert_called_once_with(
            "KXBTC-A",
            period_interval=1440,
            start_ts=mock_client.get_market_candlesticks.call_args[1]["start_ts"],
            end_ts=mock_client.get_market_candlesticks.call_args[1]["end_ts"],
            historical=True,
        )

    def test_continues_when_individual_ticker_raises_api_error(self, collector, mock_client, mock_store):
        mock_store.get_markets.return_value = _markets_df([
            ("KXBTC-A", "2020-01-01T00:00:00Z"),
            ("KXBTC-B", "2020-01-02T00:00:00Z"),
        ])
        future_cutoff = int(__import__("datetime").datetime(2099, 1, 1).timestamp())
        mock_client.get_historical_cutoff.return_value = {"live_cutoff_ts": future_cutoff}
        mock_client.get_market_candlesticks.side_effect = [
            KalshiAPIError("not found", status_code=404),
            {"candlesticks": [_candle()]},
        ]

        # Should not raise; both tickers should appear in results
        result = collector.collect_candlesticks(["KXBTC-A", "KXBTC-B"])
        assert "KXBTC-A" in result
        assert "KXBTC-B" in result

    def test_batches_live_tickers_in_chunks_of_100(self, collector, mock_client, mock_store):
        tickers = [f"KXBTC-{i:03d}" for i in range(150)]
        # All live (no settlement info in store → defaults to live)
        mock_store.get_markets.return_value = _empty_df()
        mock_client.get_historical_cutoff.return_value = {"live_cutoff_ts": 1000}
        mock_client.get_batch_candlesticks.return_value = {"candlesticks": {}}

        collector.collect_candlesticks(tickers)
        assert mock_client.get_batch_candlesticks.call_count == 2  # 100 + 50

    def test_prints_start_line_and_progress_for_live_tickers(
        self, collector, mock_client, mock_store, capsys
    ):
        mock_store.get_markets.return_value = _empty_df()
        mock_client.get_historical_cutoff.return_value = {"live_cutoff_ts": 1000}
        mock_client.get_batch_candlesticks.return_value = {"candlesticks": {}}

        collector.collect_candlesticks(["KXBTC-A", "KXBTC-B"])
        out = capsys.readouterr().out

        lines = [l for l in out.splitlines() if "[collect] Fetching candles" in l]
        # start line + one progress line after the single batch
        assert len(lines) == 2
        assert "2 live batch" in lines[0]
        assert "2/2 done" in lines[1]
        assert "2 live batch" in lines[1]

    def test_prints_progress_for_historical_tickers_at_batch_boundaries(
        self, collector, mock_client, mock_store, capsys
    ):
        # 150 historical tickers → progress after every 100 + final
        tickers = [f"KXBTC-{i:03d}" for i in range(150)]
        future_cutoff = int(__import__("datetime").datetime(2099, 1, 1).timestamp())
        mock_store.get_markets.return_value = _markets_df(
            [(t, "2020-01-01T00:00:00Z") for t in tickers]
        )
        mock_client.get_historical_cutoff.return_value = {"live_cutoff_ts": future_cutoff}
        mock_client.get_market_candlesticks.return_value = {"candlesticks": []}

        collector.collect_candlesticks(tickers)
        out = capsys.readouterr().out

        progress_lines = [l for l in out.splitlines() if "done" in l]
        # progress after ticker 100, then after ticker 150 (final)
        assert len(progress_lines) == 2
        assert "100/150" in progress_lines[0]
        assert "150/150" in progress_lines[1]

    def test_routes_via_close_time_when_settlement_ts_absent(self, collector, mock_client, mock_store):
        """Markets without settlement_ts fall back to close_time for live/historical routing."""
        # close_time is in 2020 → should be routed to historical endpoint
        future_cutoff = int(__import__("datetime").datetime(2099, 1, 1).timestamp())
        mock_store.get_markets.return_value = _markets_df_with_close_time([
            ("KXBTC-A", "", "2020-01-01T00:00:00Z"),  # empty settlement_ts
        ])
        mock_client.get_historical_cutoff.return_value = {"live_cutoff_ts": future_cutoff}
        mock_client.get_market_candlesticks.return_value = {"candlesticks": [_candle()]}

        collector.collect_candlesticks(["KXBTC-A"])
        mock_client.get_market_candlesticks.assert_called_once()
        mock_client.get_batch_candlesticks.assert_not_called()


# ---------------------------------------------------------------------------
# run
# ---------------------------------------------------------------------------

class TestRun:
    def test_run_returns_collection_summary(self, collector, mock_client, mock_store):
        mock_client.get_markets.return_value = {
            "markets": [_market_dict("KXBTC-A", close_time="2025-12-01T00:00:00Z")],
            "cursor": "",
        }
        mock_client.get_historical_markets.return_value = {"markets": [], "cursor": ""}
        mock_client.get_historical_cutoff.return_value = {"live_cutoff_ts": 1000}
        mock_client.get_batch_candlesticks.return_value = {
            "candlesticks": {"KXBTC-A": [_candle()]}
        }
        mock_store.save_markets.return_value = 1
        mock_store.save_candles.return_value = 1

        summary = collector.run(series_tickers=["KXBTC"], days_back=180)
        assert isinstance(summary, CollectionSummary)
        assert summary.markets_found >= 0

    def test_run_prints_summary(self, collector, mock_client, mock_store, capsys):
        mock_client.get_markets.return_value = {"markets": [], "cursor": ""}
        mock_client.get_historical_markets.return_value = {"markets": [], "cursor": ""}

        collector.run(series_tickers=["KXBTC"])
        out = capsys.readouterr().out
        assert "[collect]" in out
        assert "Done" in out

    def test_markets_new_reflects_save_markets_return_value(self, collector, mock_client, mock_store):
        """markets_new must come from save_markets, not from candle presence."""
        mock_client.get_markets.return_value = {
            "markets": [_market_dict("KXBTC-A", close_time="2025-12-01T00:00:00Z")],
            "cursor": "",
        }
        mock_client.get_historical_markets.return_value = {"markets": [], "cursor": ""}
        mock_client.get_historical_cutoff.return_value = {"live_cutoff_ts": 1000}
        mock_client.get_batch_candlesticks.return_value = {"candlesticks": {}}
        # save_markets says 0 new (already existed in markets.csv)
        mock_store.save_markets.return_value = 0

        summary = collector.run(series_tickers=["KXBTC"], days_back=180)
        assert summary.markets_new == 0
