"""Tests for data/data_store.py (Task 10)."""

import os
import sys

import pandas as pd
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from data.data_store import DataStore


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _market(ticker="KXBTC-25DEC", series_ticker="KXBTC", status="settled"):
    return {
        "ticker": ticker,
        "event_ticker": "KXBTC-25",
        "series_ticker": series_ticker,
        "title": f"Test market {ticker}",
        "market_type": "binary",
        "status": status,
        "result": "yes",
        "settlement_value_dollars": 1.0,
        "open_time": "2025-01-01T00:00:00Z",
        "close_time": "2025-12-31T00:00:00Z",
        "settlement_ts": "2025-12-31T12:00:00Z",
    }


def _candle(end_period_ts=1701388800, close=51):
    return {
        "end_period_ts": end_period_ts,
        "price": {"open": 42, "high": 55, "low": 38, "close": close},
        "yes_bid": {"open": 41, "high": 54, "low": 37, "close": close - 1},
        "yes_ask": {"open": 43, "high": 56, "low": 39, "close": close + 1},
        "volume": 1200,
        "open_interest": 3400,
    }


@pytest.fixture
def store(tmp_path):
    return DataStore(
        markets_path=str(tmp_path / "markets.csv"),
        candles_path=str(tmp_path / "candles.csv"),
    )


# ---------------------------------------------------------------------------
# save_markets
# ---------------------------------------------------------------------------

class TestSaveMarkets:
    def test_creates_file_on_first_call(self, store):
        store.save_markets([_market()])
        assert os.path.exists(store.markets_path)

    def test_returns_count_of_new_rows(self, store):
        count = store.save_markets([_market("KXBTC-A"), _market("KXBTC-B")])
        assert count == 2

    def test_upsert_duplicate_ticker_not_appended(self, store):
        store.save_markets([_market("KXBTC-A")])
        store.save_markets([_market("KXBTC-A")])
        df = pd.read_csv(store.markets_path)
        assert len(df[df["ticker"] == "KXBTC-A"]) == 1

    def test_upsert_new_ticker_returns_1(self, store):
        store.save_markets([_market("KXBTC-A")])
        count = store.save_markets([_market("KXBTC-B")])
        assert count == 1

    def test_duplicate_ticker_returns_0(self, store):
        store.save_markets([_market("KXBTC-A")])
        count = store.save_markets([_market("KXBTC-A")])
        assert count == 0

    def test_settlement_value_dollars_converted_to_cents(self, store):
        m = _market()
        m["settlement_value_dollars"] = 0.75
        store.save_markets([m])
        df = pd.read_csv(store.markets_path)
        assert df.iloc[0]["settlement_value_cents"] == 75

    def test_empty_list_returns_0_and_no_file_created(self, store):
        count = store.save_markets([])
        assert count == 0
        assert not os.path.exists(store.markets_path)

    def test_missing_settlement_value_defaults_to_zero(self, store):
        m = _market()
        del m["settlement_value_dollars"]
        store.save_markets([m])
        df = pd.read_csv(store.markets_path)
        assert df.iloc[0]["settlement_value_cents"] == 0


# ---------------------------------------------------------------------------
# save_candles
# ---------------------------------------------------------------------------

class TestSaveCandles:
    def test_creates_file_on_first_call(self, store):
        store.save_candles("KXBTC-A", [_candle()], granularity=1440)
        assert os.path.exists(store.candles_path)

    def test_returns_count_of_new_rows(self, store):
        count = store.save_candles("KXBTC-A", [_candle(1000), _candle(2000)], granularity=1440)
        assert count == 2

    def test_upsert_deduplicates_on_composite_key(self, store):
        store.save_candles("KXBTC-A", [_candle(1000)], granularity=1440)
        store.save_candles("KXBTC-A", [_candle(1000)], granularity=1440)
        df = pd.read_csv(store.candles_path)
        assert len(df) == 1

    def test_duplicate_returns_0(self, store):
        store.save_candles("KXBTC-A", [_candle(1000)], granularity=1440)
        count = store.save_candles("KXBTC-A", [_candle(1000)], granularity=1440)
        assert count == 0

    def test_same_period_different_granularity_not_deduplicated(self, store):
        store.save_candles("KXBTC-A", [_candle(1000)], granularity=1440)
        count = store.save_candles("KXBTC-A", [_candle(1000)], granularity=60)
        assert count == 1

    def test_candle_fields_flattened_correctly(self, store):
        store.save_candles("KXBTC-A", [_candle(end_period_ts=1701388800, close=51)], granularity=1440)
        df = pd.read_csv(store.candles_path)
        row = df.iloc[0]
        assert row["ticker"] == "KXBTC-A"
        assert row["granularity"] == 1440
        assert row["close_cents"] == 51
        assert row["volume"] == 1200
        assert row["open_interest"] == 3400
        assert row["yes_bid_cents"] == 50
        assert row["yes_ask_cents"] == 52

    def test_empty_list_returns_0(self, store):
        count = store.save_candles("KXBTC-A", [], granularity=1440)
        assert count == 0

    def test_candle_missing_end_period_ts_is_skipped(self, store):
        bad = {"price": {"open": 40, "high": 50, "low": 35, "close": 45},
               "yes_bid": {"close": 44}, "yes_ask": {"close": 46},
               "volume": 100, "open_interest": 200}
        count = store.save_candles("KXBTC-A", [bad], granularity=1440)
        assert count == 0
        assert not os.path.exists(store.candles_path)


# ---------------------------------------------------------------------------
# get_markets
# ---------------------------------------------------------------------------

class TestGetMarkets:
    def test_returns_empty_df_when_file_absent(self, store):
        df = store.get_markets()
        assert isinstance(df, pd.DataFrame)
        assert len(df) == 0
        assert "ticker" in df.columns

    def test_returns_all_markets_without_filters(self, store):
        store.save_markets([_market("KXBTC-A"), _market("KXBTC-B")])
        df = store.get_markets()
        assert len(df) == 2

    def test_filters_by_series_ticker(self, store):
        store.save_markets([
            _market("KXBTC-A", series_ticker="KXBTC"),
            _market("KXETH-A", series_ticker="KXETH"),
        ])
        df = store.get_markets(series_ticker="KXBTC")
        assert list(df["ticker"]) == ["KXBTC-A"]

    def test_filters_by_status(self, store):
        store.save_markets([
            _market("KXBTC-A", status="settled"),
            _market("KXBTC-B", status="open"),
        ])
        df = store.get_markets(status="settled")
        assert list(df["ticker"]) == ["KXBTC-A"]


# ---------------------------------------------------------------------------
# get_candles
# ---------------------------------------------------------------------------

class TestGetCandles:
    def test_returns_empty_df_when_file_absent(self, store):
        df = store.get_candles()
        assert isinstance(df, pd.DataFrame)
        assert len(df) == 0
        assert "ticker" in df.columns

    def test_returns_all_candles_without_filter(self, store):
        store.save_candles("KXBTC-A", [_candle(1000), _candle(2000)], granularity=1440)
        df = store.get_candles()
        assert len(df) == 2

    def test_filters_by_ticker(self, store):
        store.save_candles("KXBTC-A", [_candle(1000)], granularity=1440)
        store.save_candles("KXBTC-B", [_candle(2000)], granularity=1440)
        df = store.get_candles(ticker="KXBTC-A")
        assert len(df) == 1
        assert df.iloc[0]["ticker"] == "KXBTC-A"


# ---------------------------------------------------------------------------
# ticker_has_candles
# ---------------------------------------------------------------------------

class TestTickerHasCandles:
    def test_returns_false_when_file_absent(self, store):
        assert store.ticker_has_candles("KXBTC-A") is False

    def test_returns_false_when_ticker_missing(self, store):
        store.save_candles("KXBTC-B", [_candle()], granularity=1440)
        assert store.ticker_has_candles("KXBTC-A") is False

    def test_returns_true_when_ticker_present(self, store):
        store.save_candles("KXBTC-A", [_candle()], granularity=1440)
        assert store.ticker_has_candles("KXBTC-A") is True


# ---------------------------------------------------------------------------
# get_collected_tickers
# ---------------------------------------------------------------------------

class TestGetCollectedTickers:
    def test_returns_empty_set_when_file_absent(self, store):
        assert store.get_collected_tickers() == set()

    def test_returns_set_of_tickers_with_candles(self, store):
        store.save_candles("KXBTC-A", [_candle(1000)], granularity=1440)
        store.save_candles("KXBTC-B", [_candle(2000)], granularity=1440)
        assert store.get_collected_tickers() == {"KXBTC-A", "KXBTC-B"}

    def test_multiple_candles_same_ticker_counted_once(self, store):
        store.save_candles("KXBTC-A", [_candle(1000), _candle(2000)], granularity=1440)
        tickers = store.get_collected_tickers()
        assert tickers == {"KXBTC-A"}
