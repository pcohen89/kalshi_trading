# test_integration.py — Cross-module integration tests (Task 7)
"""
Tests that verify real module instances interact correctly when wired together
through MainApp.

A shared Mock KalshiClient is injected into real TradeExecutor, PortfolioTracker,
and TradeLogger instances. No live API calls are made.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from unittest.mock import Mock, patch

from main import MainApp
from cli_interface import TradingCLI
from trade_executor import TradeExecutor, TradeExecutionError
from portfolio_tracker import PortfolioTracker, PortfolioError
from trade_logger import TradeLogger
from config import ConfigurationError


# =============================================================================
# Shared fixtures
# =============================================================================

@pytest.fixture
def mock_client():
    """Shared mock KalshiClient used across all integration fixtures."""
    return Mock()


@pytest.fixture
def app(mock_client, tmp_path):
    """
    MainApp wired with real TradeExecutor, PortfolioTracker, and TradeLogger
    instances, all sharing the same mock client.
    """
    executor = TradeExecutor(client=mock_client)
    tracker = PortfolioTracker(client=mock_client)
    logger = TradeLogger(log_dir=str(tmp_path))
    return MainApp(
        client=mock_client,
        executor=executor,
        tracker=tracker,
        logger=logger,
    )


# =============================================================================
# Group 1: Dependency injection wiring
# =============================================================================

class TestDependencyInjection:

    def test_shared_client_reaches_executor(self, app, mock_client):
        """TradeExecutor holds the same client instance as MainApp."""
        assert app.executor.client is mock_client

    def test_shared_client_reaches_tracker(self, app, mock_client):
        """PortfolioTracker holds the same client instance as MainApp."""
        assert app.tracker.client is mock_client

    def test_trading_cli_gets_separate_executor(self, app):
        """TradingCLI lazily creates its own TradeExecutor, separate from app.executor."""
        with patch('cli_interface.TradeExecutor') as MockExecutor:
            cli = TradingCLI()
            cli._ensure_executor()
        # CLI's executor is the mock constructed inside TradingCLI, not app's
        assert cli.executor is not app.executor


# =============================================================================
# Group 2: Portfolio path
# =============================================================================

class TestPortfolioPath:

    def test_view_portfolio_calls_tracker(self, app):
        """_view_portfolio() delegates to the real tracker's display method."""
        with patch.object(app.tracker, 'display_portfolio_summary') as mock_display:
            app._view_portfolio()
        mock_display.assert_called_once()

    def test_view_portfolio_error_does_not_crash_menu(self, app, capsys):
        """PortfolioError from tracker is caught; menu loop stays alive."""
        call_count = 0

        def toggle_portfolio():
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise PortfolioError("simulated error")

        with patch('main.validate_config'), \
             patch.object(app.tracker, 'display_portfolio_summary',
                          side_effect=toggle_portfolio), \
             patch('builtins.input', side_effect=["1", "6"]):
            app.run()  # must not raise

        out = capsys.readouterr().out
        assert "error" in out.lower() or "Error" in out


# =============================================================================
# Group 3: Open orders path
# =============================================================================

class TestOpenOrdersPath:

    def test_view_open_orders_formats_output(self, app, mock_client, capsys):
        """get_orders result flows through executor and is printed to stdout."""
        mock_client.get_orders.return_value = {
            "orders": [
                {
                    "order_id": "int-ord-visible",
                    "ticker": "INT-TEST",
                    "side": "yes",
                    "action": "buy",
                    "status": "resting",
                    "remaining_count": 3,
                    "count": 5,
                }
            ]
        }
        app._view_open_orders()
        out = capsys.readouterr().out
        # format_order_summary truncates order_id to 12 chars; assert on ticker instead
        assert "INT-TEST" in out

    def test_view_open_orders_error_does_not_crash_menu(self, app, capsys):
        """TradeExecutionError from list_open_orders is caught; no crash."""
        with patch.object(app.executor, 'list_open_orders',
                          side_effect=TradeExecutionError("API down")):
            app._view_open_orders()  # must not raise
        out = capsys.readouterr().out
        assert "error" in out.lower() or "Error" in out


# =============================================================================
# Group 4: Cancel order path
# =============================================================================

class TestCancelOrderPath:

    def test_cancel_order_calls_executor(self, app, mock_client):
        """Confirmed cancellation reaches client.cancel_order with correct id."""
        mock_client.cancel_order.return_value = {"order": {"status": "cancelled"}}
        with patch('builtins.input', side_effect=["cancel-ord-1", "yes"]):
            app._cancel_order()
        mock_client.cancel_order.assert_called_once_with("cancel-ord-1")

    def test_cancel_order_error_does_not_crash_menu(self, app, capsys):
        """TradeExecutionError from cancel_order is caught; no crash."""
        with patch.object(app.executor, 'cancel_order',
                          side_effect=TradeExecutionError("not found")), \
             patch('builtins.input', side_effect=["cancel-ord-2", "yes"]):
            app._cancel_order()  # must not raise
        out = capsys.readouterr().out
        assert "error" in out.lower() or "Error" in out


# =============================================================================
# Group 5: Trade history path
# =============================================================================

class TestTradeHistoryPath:

    def test_view_trade_history_reads_logger(self, app, capsys):
        """Events logged via logger appear in display_recent_trades output."""
        app.logger.log_order_submission({
            "order": {
                "order_id": "hist-ord-1",
                "ticker": "KXBTC-HISTTEST",
                "side": "yes",
                "count": 2,
                "yes_price": 50,
            }
        })
        app._view_trade_history()
        out = capsys.readouterr().out
        assert "KXBTC-HISTTEST" in out

    def test_view_trade_history_empty_log(self, app, capsys):
        """Empty log produces 'No trade events recorded' message."""
        app._view_trade_history()
        out = capsys.readouterr().out
        assert "No trade events recorded" in out


# =============================================================================
# Group 6: Error recovery
# =============================================================================

class TestErrorRecovery:

    def test_multiple_errors_in_sequence_do_not_crash(self, app, capsys):
        """
        Sequence of portfolio error → open-orders error → successful portfolio
        view all handled gracefully; menu stays alive throughout.
        """
        portfolio_calls = 0

        def toggle_portfolio():
            nonlocal portfolio_calls
            portfolio_calls += 1
            if portfolio_calls == 1:
                raise PortfolioError("first portfolio error")
            # second call: returns None (success)

        with patch('main.validate_config'), \
             patch.object(app.tracker, 'display_portfolio_summary',
                          side_effect=toggle_portfolio), \
             patch.object(app.executor, 'list_open_orders',
                          side_effect=TradeExecutionError("orders error")), \
             patch('builtins.input', side_effect=["1", "3", "1", "6"]):
            app.run()  # must not raise

    def test_config_error_at_startup(self, app, capsys):
        """ConfigurationError from validate_config prints error and skips menu loop."""
        with patch('main.validate_config',
                   side_effect=ConfigurationError("missing KALSHI_API_KEY")), \
             patch('builtins.input') as mock_input:
            app.run()
        mock_input.assert_not_called()
        out = capsys.readouterr().out
        assert "Configuration" in out or "error" in out.lower()


# =============================================================================
# Group 7: Menu routing (real app instances)
# =============================================================================

class TestMenuRouting:

    def test_menu_choice_1_calls_view_portfolio(self, app):
        """Choice '1' routes to _view_portfolio on a real MainApp instance."""
        with patch('main.validate_config'), \
             patch('builtins.input', side_effect=["1", "6"]), \
             patch.object(app, '_view_portfolio') as mock_method:
            app.run()
        mock_method.assert_called_once()

    def test_menu_choice_5_calls_view_history(self, app):
        """Choice '5' routes to _view_trade_history on a real MainApp instance."""
        with patch('main.validate_config'), \
             patch('builtins.input', side_effect=["5", "6"]), \
             patch.object(app, '_view_trade_history') as mock_method:
            app.run()
        mock_method.assert_called_once()
