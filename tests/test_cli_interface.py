# test_cli_interface.py — Unit tests for cli_interface.py (Task 7)
"""
Tests for TradingCLI: initialization, lazy executor creation, each menu
action handler, and error handling.

All tests use mocked TradeExecutor — no live API calls are made.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from unittest.mock import Mock, patch

from cli_interface import TradingCLI, run_trading_cli
from trade_executor import TradeExecutionError


# =============================================================================
# Helper
# =============================================================================

def _cli_with_mock_executor() -> TradingCLI:
    """Return a TradingCLI whose executor is already a Mock (bypasses lazy init)."""
    cli = TradingCLI()
    cli.executor = Mock()
    return cli


# =============================================================================
# Group 1: Initialization
# =============================================================================

class TestTradingCLIInit:

    def test_init_creates_no_executor(self):
        """executor is None until first use."""
        cli = TradingCLI()
        assert cli.executor is None

    def test_ensure_executor_creates_executor_on_first_call(self):
        """Lazy init creates a TradeExecutor and assigns it."""
        with patch('cli_interface.TradeExecutor') as MockExecutor:
            cli = TradingCLI()
            result = cli._ensure_executor()
        assert result is True
        assert cli.executor is MockExecutor.return_value

    def test_ensure_executor_reuses_existing(self):
        """Second call returns True and does not construct a new executor."""
        with patch('cli_interface.TradeExecutor') as MockExecutor:
            cli = TradingCLI()
            cli._ensure_executor()
            first_executor = cli.executor
            cli._ensure_executor()
        assert cli.executor is first_executor
        assert MockExecutor.call_count == 1


# =============================================================================
# Group 2: Search markets (menu option 1)
# =============================================================================

class TestSearchMarkets:

    def test_search_markets_displays_results(self, capsys):
        """Found markets are printed with their ticker."""
        cli = _cli_with_mock_executor()
        cli.executor.search_markets.return_value = [
            {
                "ticker": "TEST-TICKER",
                "title": "Test Market Title",
                "status": "open",
                "yes_bid": 45,
                "yes_ask": 55,
                "volume_24h": 500,
            }
        ]
        with patch('builtins.input', side_effect=["test query", "1"]):
            cli._search_markets()
        out = capsys.readouterr().out
        assert "TEST-TICKER" in out

    def test_search_markets_no_results(self, capsys):
        """Empty results with no query prints 'No markets found' message."""
        cli = _cli_with_mock_executor()
        cli.executor.search_markets.return_value = []
        with patch('builtins.input', side_effect=["", "1"]):
            cli._search_markets()
        out = capsys.readouterr().out
        assert "No markets found" in out

    def test_search_markets_api_error(self, capsys):
        """TradeExecutionError is caught and printed; menu loop continues."""
        cli = _cli_with_mock_executor()
        cli.executor.search_markets.side_effect = TradeExecutionError("API error")
        with patch('builtins.input', side_effect=["test", "1"]):
            cli._search_markets()  # must not raise
        out = capsys.readouterr().out
        assert "Error" in out or "error" in out.lower()


# =============================================================================
# Group 3: Place market order (menu option 2)
# =============================================================================

class TestPlaceMarketOrder:

    def _open_market(self) -> dict:
        return {"ticker": "TEST-MKT", "status": "open", "yes_bid": 45, "yes_ask": 55}

    def test_place_market_order_success(self, capsys):
        """Valid inputs place order and display order_id."""
        cli = _cli_with_mock_executor()
        cli.executor.get_market_info.return_value = self._open_market()
        cli.executor.place_market_order.return_value = {
            "order": {"order_id": "ord123abc", "status": "resting"}
        }
        with patch('builtins.input', side_effect=["TEST-MKT", "yes", "5", "yes"]):
            cli._place_market_order()
        cli.executor.place_market_order.assert_called_once_with("TEST-MKT", "yes", 5)
        out = capsys.readouterr().out
        assert "ord123abc" in out

    def test_place_market_order_confirmation_rejected(self):
        """User enters 'n' at confirm prompt — order never placed."""
        cli = _cli_with_mock_executor()
        cli.executor.get_market_info.return_value = self._open_market()
        with patch('builtins.input', side_effect=["TEST-MKT", "yes", "5", "n"]):
            cli._place_market_order()
        cli.executor.place_market_order.assert_not_called()

    def test_place_market_order_invalid_side(self, capsys):
        """Side other than 'yes'/'no' rejected before order placement."""
        cli = _cli_with_mock_executor()
        cli.executor.get_market_info.return_value = self._open_market()
        with patch('builtins.input', side_effect=["TEST-MKT", "maybe"]):
            cli._place_market_order()
        cli.executor.place_market_order.assert_not_called()
        out = capsys.readouterr().out
        assert "yes" in out.lower() or "no" in out.lower() or "side" in out.lower()

    def test_place_market_order_api_error(self, capsys):
        """TradeExecutionError from place_market_order is caught and printed."""
        cli = _cli_with_mock_executor()
        cli.executor.get_market_info.return_value = self._open_market()
        cli.executor.place_market_order.side_effect = TradeExecutionError("insufficient funds")
        with patch('builtins.input', side_effect=["TEST-MKT", "yes", "5", "yes"]):
            cli._place_market_order()  # must not raise
        out = capsys.readouterr().out
        assert "insufficient funds" in out or "Error" in out


# =============================================================================
# Group 4: Place limit order (menu option 3)
# =============================================================================

class TestPlaceLimitOrder:

    def _open_market(self) -> dict:
        return {"ticker": "TEST-LMT", "status": "open", "yes_bid": 45, "yes_ask": 55}

    def test_place_limit_order_success(self):
        """Valid inputs place limit order with correct price."""
        cli = _cli_with_mock_executor()
        cli.executor.get_market_info.return_value = self._open_market()
        cli.executor.place_limit_order.return_value = {
            "order": {"order_id": "lmt456", "status": "resting"}
        }
        with patch('builtins.input', side_effect=["TEST-LMT", "yes", "5", "50", "yes"]):
            cli._place_limit_order()
        cli.executor.place_limit_order.assert_called_once_with("TEST-LMT", "yes", 5, 50)

    def test_place_limit_order_price_out_of_range(self, capsys):
        """Price 0 is rejected with an error; next valid price is accepted."""
        cli = _cli_with_mock_executor()
        cli.executor.get_market_info.return_value = self._open_market()
        cli.executor.place_limit_order.return_value = {
            "order": {"order_id": "lmt456", "status": "resting"}
        }
        # 0 rejected → 50 accepted → confirmed
        with patch('builtins.input', side_effect=["TEST-LMT", "yes", "5", "0", "50", "yes"]):
            cli._place_limit_order()
        cli.executor.place_limit_order.assert_called_once_with("TEST-LMT", "yes", 5, 50)
        out = capsys.readouterr().out
        assert "at least 1" in out or "at most 99" in out  # bounds error shown for 0

    def test_place_limit_order_confirmation_rejected(self):
        """User enters 'n' at confirm prompt — order never placed."""
        cli = _cli_with_mock_executor()
        cli.executor.get_market_info.return_value = self._open_market()
        with patch('builtins.input', side_effect=["TEST-LMT", "yes", "5", "50", "n"]):
            cli._place_limit_order()
        cli.executor.place_limit_order.assert_not_called()

    def test_place_limit_order_api_error(self, capsys):
        """TradeExecutionError from place_limit_order is caught and printed."""
        cli = _cli_with_mock_executor()
        cli.executor.get_market_info.return_value = self._open_market()
        cli.executor.place_limit_order.side_effect = TradeExecutionError("API error")
        with patch('builtins.input', side_effect=["TEST-LMT", "yes", "5", "50", "yes"]):
            cli._place_limit_order()  # must not raise
        out = capsys.readouterr().out
        assert "Error" in out or "error" in out.lower()


# =============================================================================
# Group 5: View open orders (menu option 4)
# =============================================================================

class TestViewOpenOrders:

    def test_view_open_orders_with_orders(self, capsys):
        """Found orders are printed via format_order_summary."""
        cli = _cli_with_mock_executor()
        cli.executor.list_open_orders.return_value = [
            {
                "order_id": "ord-visible",
                "ticker": "T-MKT",
                "side": "yes",
                "action": "buy",
                "status": "resting",
                "count": 5,
                "remaining_count": 5,
            }
        ]
        cli._view_open_orders()
        out = capsys.readouterr().out
        assert "ord-visible" in out

    def test_view_open_orders_empty(self, capsys):
        """Empty list prints 'No open orders' message."""
        cli = _cli_with_mock_executor()
        cli.executor.list_open_orders.return_value = []
        cli._view_open_orders()
        out = capsys.readouterr().out
        assert "No open orders" in out

    def test_view_open_orders_api_error(self, capsys):
        """TradeExecutionError is caught and printed; no crash."""
        cli = _cli_with_mock_executor()
        cli.executor.list_open_orders.side_effect = TradeExecutionError("API down")
        cli._view_open_orders()  # must not raise
        out = capsys.readouterr().out
        assert "Error" in out or "error" in out.lower()


# =============================================================================
# Group 6: Cancel order (menu option 5)
# =============================================================================

class TestCancelOrder:

    def test_cancel_order_success(self):
        """Confirmed cancellation calls executor.cancel_order with the given id."""
        cli = _cli_with_mock_executor()
        cli.executor.list_open_orders.return_value = []
        cli.executor.cancel_order.return_value = {"order": {"status": "cancelled"}}
        with patch('builtins.input', side_effect=["ord-123", "yes"]):
            cli._cancel_order()
        cli.executor.cancel_order.assert_called_once_with("ord-123")

    def test_cancel_order_confirmation_rejected(self):
        """User enters 'n' at confirm prompt — cancel_order never called."""
        cli = _cli_with_mock_executor()
        cli.executor.list_open_orders.return_value = []
        with patch('builtins.input', side_effect=["ord-456", "n"]):
            cli._cancel_order()
        cli.executor.cancel_order.assert_not_called()

    def test_cancel_order_api_error(self, capsys):
        """TradeExecutionError from cancel_order is caught and printed."""
        cli = _cli_with_mock_executor()
        cli.executor.list_open_orders.return_value = []
        cli.executor.cancel_order.side_effect = TradeExecutionError("order not found")
        with patch('builtins.input', side_effect=["ord-789", "yes"]):
            cli._cancel_order()  # must not raise
        out = capsys.readouterr().out
        assert "Error" in out or "order not found" in out


# =============================================================================
# Group 7: Check order status (menu option 6)
# =============================================================================

class TestCheckOrderStatus:

    def test_check_order_status_success(self, capsys):
        """Order status fields are printed including order_id."""
        cli = _cli_with_mock_executor()
        cli.executor.get_order_status.return_value = {
            "order": {
                "order_id": "ord-status-test",
                "ticker": "T-MKT",
                "side": "yes",
                "action": "buy",
                "status": "resting",
                "count": 10,
                "remaining_count": 8,
            }
        }
        with patch('builtins.input', side_effect=["ord-status-test"]):
            cli._check_order_status()
        out = capsys.readouterr().out
        assert "ord-status-test" in out

    def test_check_order_status_api_error(self, capsys):
        """TradeExecutionError from get_order_status is caught and printed."""
        cli = _cli_with_mock_executor()
        cli.executor.get_order_status.side_effect = TradeExecutionError("order not found")
        with patch('builtins.input', side_effect=["ord-xyz"]):
            cli._check_order_status()  # must not raise
        out = capsys.readouterr().out
        assert "Error" in out or "order not found" in out


# =============================================================================
# Group 8: Menu loop
# =============================================================================

class TestMenuLoop:

    def test_invalid_menu_choice_shows_error(self, capsys):
        """Non-numeric or out-of-range input prints 'Invalid choice' message."""
        cli = TradingCLI()
        with patch('builtins.input', side_effect=["invalid", "7"]):
            cli.run()
        out = capsys.readouterr().out
        assert "Invalid" in out or "invalid" in out.lower()

    def test_exit_choice_returns(self):
        """Choice '7' exits the loop cleanly without raising."""
        cli = TradingCLI()
        with patch('builtins.input', side_effect=["7"]):
            cli.run()  # must return, not raise

    def test_keyboard_interrupt_exits_cleanly(self, capsys):
        """KeyboardInterrupt during input is caught by run_trading_cli wrapper."""
        with patch('builtins.input', side_effect=KeyboardInterrupt()):
            run_trading_cli()  # must not raise
        out = capsys.readouterr().out
        assert "Interrupted" in out or "Goodbye" in out
