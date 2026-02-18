# test_trade_logger.py - Unit tests for trade logger (Task 4)
"""
Unit tests for the TradeLogger class.

Uses tmp_path pytest fixture for isolated log directories.
No mock client needed — TradeLogger has no API dependency.
"""

import csv
import json

import pytest

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import datetime, timedelta, timezone

from trade_logger import (
    CSV_COLUMNS,
    TradeEvent,
    TradeEventType,
    TradeLogger,
    TradeLoggerError,
)


@pytest.fixture
def logger(tmp_path):
    """Create a TradeLogger with an isolated temp directory."""
    return TradeLogger(log_dir=str(tmp_path))


@pytest.fixture
def sample_order():
    """Sample order API response."""
    return {
        "order": {
            "order_id": "abc123",
            "ticker": "KXBTC-26FEB17",
            "side": "yes",
            "count": 5,
            "yes_price": 42,
        }
    }


@pytest.fixture
def sample_fill():
    """Sample fill data."""
    return {
        "order_id": "abc123",
        "ticker": "KXBTC-26FEB17",
        "side": "yes",
        "count": 5,
        "yes_price": 42,
    }


# =============================================================================
# Order Submission Tests
# =============================================================================

class TestLogOrderSubmission:
    """Tests for log_order_submission method."""

    def test_log_order_submission_returns_event(self, logger, sample_order):
        """Submission returns a TradeEvent with correct fields."""
        event = logger.log_order_submission(sample_order)
        assert event.event_type == TradeEventType.SUBMISSION.value
        assert event.order_id == "abc123"
        assert event.ticker == "KXBTC-26FEB17"
        assert event.side == "yes"
        assert event.quantity == 5
        assert event.price == 42

    def test_log_order_submission_unwrapped(self, logger):
        """Handles order dict not wrapped in {'order': ...}."""
        order = {"order_id": "xyz", "ticker": "TEST", "side": "no",
                 "count": 3, "yes_price": 60}
        event = logger.log_order_submission(order)
        assert event.order_id == "xyz"
        assert event.ticker == "TEST"
        assert event.side == "no"

    def test_log_order_submission_writes_jsonl(self, logger, sample_order, tmp_path):
        """Submission is written to JSONL file."""
        logger.log_order_submission(sample_order)
        jsonl = tmp_path / "trades.jsonl"
        assert jsonl.exists()
        line = json.loads(jsonl.read_text().strip())
        assert line["event_type"] == "submission"
        assert line["order_id"] == "abc123"

    def test_log_order_submission_writes_log(self, logger, sample_order, tmp_path):
        """Submission is written to trades.log."""
        logger.log_order_submission(sample_order)
        log_file = tmp_path / "trades.log"
        assert log_file.exists()
        content = log_file.read_text()
        assert "SUBMISSION" in content
        assert "abc123" in content

    def test_log_order_submission_utc_timestamp(self, logger, sample_order):
        """Timestamp is UTC ISO 8601."""
        event = logger.log_order_submission(sample_order)
        ts = datetime.fromisoformat(event.timestamp)
        assert ts.tzinfo is not None


# =============================================================================
# Order Fill Tests
# =============================================================================

class TestLogOrderFill:
    """Tests for log_order_fill method."""

    def test_log_order_fill_returns_event(self, logger, sample_fill):
        """Fill returns a TradeEvent with fill fields populated."""
        event = logger.log_order_fill(sample_fill)
        assert event.event_type == TradeEventType.FILL.value
        assert event.order_id == "abc123"
        assert event.fill_price == 42
        assert event.quantity_filled == 5

    def test_log_order_fill_writes_jsonl(self, logger, sample_fill, tmp_path):
        """Fill is written to JSONL file."""
        logger.log_order_fill(sample_fill)
        jsonl = tmp_path / "trades.jsonl"
        line = json.loads(jsonl.read_text().strip())
        assert line["event_type"] == "fill"
        assert line["fill_price"] == 42

    def test_log_order_fill_fallback_keys(self, logger):
        """Fill uses fallback keys (fill_price, quantity_filled)."""
        fill = {"order_id": "f1", "ticker": "T", "side": "yes",
                "fill_price": 55, "quantity_filled": 3, "price": 55, "quantity": 3}
        event = logger.log_order_fill(fill)
        assert event.fill_price == 55
        assert event.quantity_filled == 3


# =============================================================================
# Order Cancellation Tests
# =============================================================================

class TestLogOrderCancellation:
    """Tests for log_order_cancellation method."""

    def test_log_order_cancellation_returns_event(self, logger):
        """Cancellation returns a TradeEvent with order_id."""
        event = logger.log_order_cancellation("cancel-id-99")
        assert event.event_type == TradeEventType.CANCELLATION.value
        assert event.order_id == "cancel-id-99"

    def test_log_order_cancellation_writes_jsonl(self, logger, tmp_path):
        """Cancellation is written to JSONL file."""
        logger.log_order_cancellation("cancel-id-99")
        jsonl = tmp_path / "trades.jsonl"
        line = json.loads(jsonl.read_text().strip())
        assert line["event_type"] == "cancellation"
        assert line["order_id"] == "cancel-id-99"


# =============================================================================
# Error Logging Tests
# =============================================================================

class TestLogError:
    """Tests for log_error method."""

    def test_log_error_returns_event(self, logger):
        """Error returns a TradeEvent with error_message."""
        event = logger.log_error("Connection timeout")
        assert event.event_type == TradeEventType.ERROR.value
        assert event.error_message == "Connection timeout"

    def test_log_error_writes_to_errors_log(self, logger, tmp_path):
        """Error is written to errors.log."""
        logger.log_error("Something broke")
        log_file = tmp_path / "errors.log"
        assert log_file.exists()
        content = log_file.read_text()
        assert "ERROR" in content
        assert "Something broke" in content

    def test_log_error_writes_jsonl(self, logger, tmp_path):
        """Error also appears in JSONL for queryable history."""
        logger.log_error("API 500")
        jsonl = tmp_path / "trades.jsonl"
        line = json.loads(jsonl.read_text().strip())
        assert line["event_type"] == "error"
        assert line["error_message"] == "API 500"

    def test_log_error_with_context(self, logger):
        """Error stores context dict in details."""
        ctx = {"ticker": "KXBTC", "status_code": 500}
        event = logger.log_error("API error", context=ctx)
        assert event.details == ctx


# =============================================================================
# Trade History Tests
# =============================================================================

class TestGetTradeHistory:
    """Tests for get_trade_history method."""

    def test_get_trade_history_returns_all(self, logger, sample_order, sample_fill):
        """Returns all events when no date filter is given."""
        logger.log_order_submission(sample_order)
        logger.log_order_fill(sample_fill)
        logger.log_error("test error")
        history = logger.get_trade_history()
        assert len(history) == 3

    def test_get_trade_history_filter_by_start(self, logger, sample_order):
        """Filters out events before start_date."""
        logger.log_order_submission(sample_order)
        # Start date in the future — should filter out everything
        future = datetime.now(timezone.utc) + timedelta(hours=1)
        history = logger.get_trade_history(start_date=future)
        assert len(history) == 0

    def test_get_trade_history_filter_by_end(self, logger, sample_order):
        """Filters out events after end_date."""
        # End date in the past — should filter out everything
        past = datetime.now(timezone.utc) - timedelta(hours=1)
        logger.log_order_submission(sample_order)
        history = logger.get_trade_history(end_date=past)
        assert len(history) == 0

    def test_get_trade_history_filter_by_range(self, logger, sample_order):
        """Filters events within a date range."""
        start = datetime.now(timezone.utc) - timedelta(hours=1)
        logger.log_order_submission(sample_order)
        end = datetime.now(timezone.utc) + timedelta(hours=1)
        history = logger.get_trade_history(start_date=start, end_date=end)
        assert len(history) == 1

    def test_get_trade_history_empty_file(self, logger):
        """Returns empty list when no events recorded."""
        history = logger.get_trade_history()
        assert history == []

    def test_get_trade_history_naive_start_raises(self, logger):
        """Raises TradeLoggerError if start_date is naive."""
        with pytest.raises(TradeLoggerError, match="start_date must be timezone-aware"):
            logger.get_trade_history(start_date=datetime(2025, 1, 1))

    def test_get_trade_history_naive_end_raises(self, logger):
        """Raises TradeLoggerError if end_date is naive."""
        with pytest.raises(TradeLoggerError, match="end_date must be timezone-aware"):
            logger.get_trade_history(end_date=datetime(2025, 1, 1))


# =============================================================================
# CSV Export Tests
# =============================================================================

class TestExportTradesToCsv:
    """Tests for export_trades_to_csv method."""

    def test_export_creates_file_with_headers(self, logger, tmp_path):
        """CSV file is created with correct headers even when empty."""
        csv_path = str(tmp_path / "export.csv")
        count = logger.export_trades_to_csv(csv_path)
        assert count == 0
        with open(csv_path) as f:
            reader = csv.DictReader(f)
            assert list(reader.fieldnames) == CSV_COLUMNS

    def test_export_includes_events(self, logger, sample_order, tmp_path):
        """CSV contains event data."""
        logger.log_order_submission(sample_order)
        csv_path = str(tmp_path / "export.csv")
        count = logger.export_trades_to_csv(csv_path)
        assert count == 1
        with open(csv_path) as f:
            reader = csv.DictReader(f)
            row = next(reader)
            assert row["event_type"] == "submission"
            assert row["order_id"] == "abc123"
            assert row["ticker"] == "KXBTC-26FEB17"
            assert row["price_cents"] == "42"

    def test_export_returns_count(self, logger, sample_order, sample_fill, tmp_path):
        """Returns the number of rows written."""
        logger.log_order_submission(sample_order)
        logger.log_order_fill(sample_fill)
        csv_path = str(tmp_path / "export.csv")
        count = logger.export_trades_to_csv(csv_path)
        assert count == 2

    def test_export_with_date_filter(self, logger, sample_order, tmp_path):
        """Respects date filter parameters."""
        logger.log_order_submission(sample_order)
        future = datetime.now(timezone.utc) + timedelta(hours=1)
        csv_path = str(tmp_path / "export.csv")
        count = logger.export_trades_to_csv(csv_path, start_date=future)
        assert count == 0


# =============================================================================
# Display Recent Trades Tests
# =============================================================================

class TestDisplayRecentTrades:
    """Tests for display_recent_trades method."""

    def test_display_prints_output(self, logger, sample_order, capsys):
        """Prints formatted trade output."""
        logger.log_order_submission(sample_order)
        logger.display_recent_trades()
        captured = capsys.readouterr()
        assert "submission" in captured.out
        assert "KXBTC-26FEB17" in captured.out

    def test_display_limits_count(self, logger, capsys):
        """Limits output to the requested count."""
        for i in range(5):
            logger.log_order_cancellation(f"order-{i}")
        logger.display_recent_trades(count=2)
        captured = capsys.readouterr()
        # Should contain 2 data lines (plus header + separator)
        lines = [l for l in captured.out.strip().split("\n") if l.strip()]
        # Header line + separator line + 2 data lines = 4
        assert len(lines) == 4

    def test_display_empty_history(self, logger, capsys):
        """Shows message when no events exist."""
        logger.display_recent_trades()
        captured = capsys.readouterr()
        assert "No trade events recorded" in captured.out


# =============================================================================
# Logger Setup Tests
# =============================================================================

class TestLoggerSetup:
    """Tests for logger initialization and setup."""

    def test_creates_directory(self, tmp_path):
        """Creates the log directory if it doesn't exist."""
        log_dir = tmp_path / "subdir" / "logs"
        TradeLogger(log_dir=str(log_dir))
        assert log_dir.exists()

    def test_falls_back_on_config_error(self, tmp_path):
        """Falls back to INFO when config module is unavailable."""
        logger = TradeLogger(log_dir=str(tmp_path))
        assert logger._log_level == "INFO"

    def test_jsonl_path_set(self, tmp_path):
        """JSONL path is set correctly."""
        logger = TradeLogger(log_dir=str(tmp_path))
        assert logger.jsonl_path == tmp_path / "trades.jsonl"


# =============================================================================
# Edge Cases
# =============================================================================

class TestEdgeCases:
    """Tests for edge cases and malformed data."""

    def test_malformed_jsonl_skipped(self, logger, tmp_path):
        """Malformed JSONL lines are skipped without crashing."""
        jsonl = tmp_path / "trades.jsonl"
        jsonl.write_text("not valid json\n")
        events = logger._read_events()
        assert events == []

    def test_multiple_events_in_jsonl(self, logger, sample_order, sample_fill):
        """Multiple events accumulate correctly in JSONL."""
        logger.log_order_submission(sample_order)
        logger.log_order_fill(sample_fill)
        logger.log_order_cancellation("c1")
        logger.log_error("err")
        events = logger._read_events()
        assert len(events) == 4
        types = [e.event_type for e in events]
        assert types == ["submission", "fill", "cancellation", "error"]

    def test_trade_event_dataclass_defaults(self):
        """TradeEvent has sensible defaults for optional fields."""
        event = TradeEvent(event_type="submission", timestamp="2025-01-01T00:00:00+00:00")
        assert event.order_id == ""
        assert event.quantity == 0
        assert event.details == {}
