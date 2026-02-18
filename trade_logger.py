# trade_logger.py - Trade logging and history (Task 4)
"""
Trade event logging with structured storage for querying and CSV export.

Uses Python's logging module with TimedRotatingFileHandler for human-readable
audit logs, plus a JSON-lines file for structured querying and CSV export.
"""

import csv
import json
import logging
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path
from typing import Optional


class TradeLoggerError(Exception):
    """Raised when trade logging operations fail."""
    pass


class TradeEventType(str, Enum):
    """Types of trade events that can be logged."""
    SUBMISSION = "submission"
    FILL = "fill"
    CANCELLATION = "cancellation"
    ERROR = "error"


@dataclass
class TradeEvent:
    """A single trade event record."""
    event_type: str
    timestamp: str
    order_id: str = ""
    ticker: str = ""
    side: str = ""
    quantity: int = 0
    price: int = 0
    fill_price: int = 0
    quantity_filled: int = 0
    error_message: str = ""
    details: dict = field(default_factory=dict)


# CSV columns for export (excludes 'details' dict)
CSV_COLUMNS = [
    "timestamp", "event_type", "order_id", "ticker", "side",
    "quantity", "price_cents", "fill_price_cents", "quantity_filled",
    "error_message",
]


class TradeLogger:
    """
    Logs trade events to rotating log files and a structured JSONL store.

    Provides querying by date range and CSV export.
    """

    DEFAULT_LOG_DIR = "logs"

    def __init__(self, log_dir: str = None):
        self.log_dir = Path(log_dir) if log_dir else Path(self.DEFAULT_LOG_DIR)
        self.log_dir.mkdir(parents=True, exist_ok=True)

        self.jsonl_path = self.log_dir / "trades.jsonl"
        self._log_level = self._get_log_level()
        self._setup_loggers()

    # ------------------------------------------------------------------
    # Public methods
    # ------------------------------------------------------------------

    def log_order_submission(self, order_details: dict) -> TradeEvent:
        """Log an order submission event.

        Args:
            order_details: API response dict, may be wrapped as {"order": {...}}.

        Returns:
            The created TradeEvent.
        """
        order = order_details.get("order", order_details)
        event = TradeEvent(
            event_type=TradeEventType.SUBMISSION.value,
            timestamp=datetime.now(timezone.utc).isoformat(),
            order_id=str(order.get("order_id", "")),
            ticker=str(order.get("ticker", "")),
            side=str(order.get("side", "")),
            quantity=int(order.get("count", order.get("quantity", 0))),
            price=int(order.get("yes_price", order.get("price", 0))),
        )
        self._write_event(event)
        return event

    def log_order_fill(self, fill_details: dict) -> TradeEvent:
        """Log an order fill event.

        Args:
            fill_details: Dict with fill data (order_id, ticker, side, etc.).

        Returns:
            The created TradeEvent.
        """
        event = TradeEvent(
            event_type=TradeEventType.FILL.value,
            timestamp=datetime.now(timezone.utc).isoformat(),
            order_id=str(fill_details.get("order_id", "")),
            ticker=str(fill_details.get("ticker", "")),
            side=str(fill_details.get("side", "")),
            quantity=int(fill_details.get("count", fill_details.get("quantity", 0))),
            price=int(fill_details.get("yes_price", fill_details.get("price", 0))),
            fill_price=int(fill_details.get("yes_price", fill_details.get("fill_price", 0))),
            quantity_filled=int(fill_details.get("count", fill_details.get("quantity_filled", 0))),
        )
        self._write_event(event)
        return event

    def log_order_cancellation(self, order_id: str) -> TradeEvent:
        """Log an order cancellation event.

        Args:
            order_id: The ID of the cancelled order.

        Returns:
            The created TradeEvent.
        """
        event = TradeEvent(
            event_type=TradeEventType.CANCELLATION.value,
            timestamp=datetime.now(timezone.utc).isoformat(),
            order_id=str(order_id),
        )
        self._write_event(event)
        return event

    def log_error(self, error_message: str, context: dict = None) -> TradeEvent:
        """Log an error event.

        Args:
            error_message: Description of the error.
            context: Optional dict with additional context.

        Returns:
            The created TradeEvent.
        """
        event = TradeEvent(
            event_type=TradeEventType.ERROR.value,
            timestamp=datetime.now(timezone.utc).isoformat(),
            error_message=str(error_message),
            details=context or {},
        )
        self._write_event(event)
        return event

    def get_trade_history(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> list:
        """Retrieve trade events, optionally filtered by date range.

        Args:
            start_date: Inclusive start (must be timezone-aware).
            end_date: Inclusive end (must be timezone-aware).

        Returns:
            List of TradeEvent objects matching the filter.

        Raises:
            TradeLoggerError: If naive datetimes are passed.
        """
        if start_date and start_date.tzinfo is None:
            raise TradeLoggerError(
                "start_date must be timezone-aware (e.g. datetime.now(timezone.utc))"
            )
        if end_date and end_date.tzinfo is None:
            raise TradeLoggerError(
                "end_date must be timezone-aware (e.g. datetime.now(timezone.utc))"
            )

        events = self._read_events()

        if not start_date and not end_date:
            return events

        filtered = []
        for ev in events:
            ts = datetime.fromisoformat(ev.timestamp)
            if start_date and ts < start_date:
                continue
            if end_date and ts > end_date:
                continue
            filtered.append(ev)
        return filtered

    def export_trades_to_csv(
        self,
        filename: str,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> int:
        """Export trade history to a CSV file.

        Args:
            filename: Output CSV file path.
            start_date: Optional start date filter (timezone-aware).
            end_date: Optional end date filter (timezone-aware).

        Returns:
            Number of rows written (excluding header).
        """
        events = self.get_trade_history(start_date=start_date, end_date=end_date)

        with open(filename, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=CSV_COLUMNS)
            writer.writeheader()
            for ev in events:
                writer.writerow({
                    "timestamp": ev.timestamp,
                    "event_type": ev.event_type,
                    "order_id": ev.order_id,
                    "ticker": ev.ticker,
                    "side": ev.side,
                    "quantity": ev.quantity,
                    "price_cents": ev.price,
                    "fill_price_cents": ev.fill_price,
                    "quantity_filled": ev.quantity_filled,
                    "error_message": ev.error_message,
                })
        return len(events)

    def display_recent_trades(self, count: int = 20) -> None:
        """Print the most recent trade events to stdout.

        Args:
            count: Number of recent events to display (default 20).
        """
        events = self._read_events()
        recent = events[-count:] if len(events) > count else events

        if not recent:
            print("No trade events recorded.")
            return

        # Header
        print(f"\n{'Timestamp':<28} {'Type':<14} {'Ticker':<18} {'Side':<6} "
              f"{'Qty':>5} {'Price':>7} {'Details'}")
        print("-" * 100)

        for ev in recent:
            details = ""
            if ev.event_type == TradeEventType.FILL.value:
                details = f"filled {ev.quantity_filled} @ {ev.fill_price}c"
            elif ev.event_type == TradeEventType.ERROR.value:
                details = ev.error_message[:40]
            elif ev.event_type == TradeEventType.CANCELLATION.value:
                details = f"order_id={ev.order_id}"

            price_str = f"{ev.price}c" if ev.price else ""
            print(f"{ev.timestamp:<28} {ev.event_type:<14} {ev.ticker:<18} "
                  f"{ev.side:<6} {ev.quantity:>5} {price_str:>7} {details}")

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _setup_loggers(self) -> None:
        """Configure dedicated loggers with rotating file handlers."""
        level = getattr(logging, self._log_level, logging.INFO)

        # Use log_dir in logger name to avoid handler conflicts across instances
        suffix = str(self.log_dir).replace("/", ".").replace("\\", ".")

        # Trade logger
        self._trade_logger = logging.getLogger(f"kalshi.trades.{suffix}")
        self._trade_logger.setLevel(level)
        self._trade_logger.propagate = False
        if not self._trade_logger.handlers:
            handler = TimedRotatingFileHandler(
                self.log_dir / "trades.log",
                when="midnight",
                utc=True,
                backupCount=30,
            )
            handler.setFormatter(logging.Formatter("%(message)s"))
            self._trade_logger.addHandler(handler)

        # Error logger
        self._error_logger = logging.getLogger(f"kalshi.errors.{suffix}")
        self._error_logger.setLevel(level)
        self._error_logger.propagate = False
        if not self._error_logger.handlers:
            handler = TimedRotatingFileHandler(
                self.log_dir / "errors.log",
                when="midnight",
                utc=True,
                backupCount=90,
            )
            handler.setFormatter(logging.Formatter("%(message)s"))
            self._error_logger.addHandler(handler)

    def _get_log_level(self) -> str:
        """Get log level from config, with fallback to INFO."""
        try:
            from config import get_log_level
            return get_log_level()
        except Exception:
            return "INFO"

    def _write_event(self, event: TradeEvent) -> None:
        """Write an event to log files and JSONL store."""
        msg = self._format_event_message(event)

        if event.event_type == TradeEventType.ERROR.value:
            self._error_logger.error(msg)
        else:
            self._trade_logger.info(msg)

        # Always append to JSONL
        with open(self.jsonl_path, "a") as f:
            f.write(json.dumps(asdict(event)) + "\n")

    def _format_event_message(self, event: TradeEvent) -> str:
        """Format an event as a human-readable log line."""
        ts = event.timestamp
        etype = event.event_type.upper()

        if event.event_type == TradeEventType.SUBMISSION.value:
            side_str = f"BUY {event.quantity} {event.side.upper()}" if event.side else ""
            price_str = f" @ {event.price}c" if event.price else ""
            return (f"{ts} | INFO | {etype} | {side_str}{price_str} | "
                    f"{event.ticker} | order_id={event.order_id}")

        if event.event_type == TradeEventType.FILL.value:
            return (f"{ts} | INFO | {etype} | {event.quantity_filled} filled "
                    f"@ {event.fill_price}c | {event.ticker} | "
                    f"order_id={event.order_id}")

        if event.event_type == TradeEventType.CANCELLATION.value:
            return f"{ts} | INFO | {etype} | order_id={event.order_id}"

        if event.event_type == TradeEventType.ERROR.value:
            return f"{ts} | ERROR | {etype} | {event.error_message}"

        return f"{ts} | INFO | {etype} | {event.order_id}"

    def _read_events(self) -> list:
        """Read all events from the JSONL file.

        Returns:
            List of TradeEvent objects. Malformed lines are skipped with a warning.
        """
        if not self.jsonl_path.exists():
            return []

        events = []
        with open(self.jsonl_path, "r") as f:
            for line_num, line in enumerate(f, 1):
                line = line.strip()
                if not line:
                    continue
                try:
                    data = json.loads(line)
                    events.append(TradeEvent(**data))
                except (json.JSONDecodeError, TypeError) as e:
                    self._error_logger.warning(
                        f"Skipping malformed JSONL line {line_num}: {e}"
                    )
        return events
