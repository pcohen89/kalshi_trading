# test_main.py — Unit tests for main.py (Task 6)
"""
Tests for MainApp: initialization, menu routing, each action handler,
and the module-level entry point.

All tests use mocked dependencies — no live API calls are made.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from unittest.mock import Mock, patch, call

from main import MainApp, main as run_main
from config import ConfigurationError
from trade_executor import TradeExecutionError
from portfolio_tracker import PortfolioError


# =============================================================================
# Shared fixture
# =============================================================================

@pytest.fixture
def app():
    """MainApp with all four dependencies mocked out."""
    return MainApp(
        client=Mock(),
        executor=Mock(),
        tracker=Mock(),
        logger=Mock(),
    )


# =============================================================================
# Group 1: Initialization
# =============================================================================

class TestMainAppInit:

    def test_init_creates_default_client_when_none_passed(self):
        with patch('main.KalshiClient') as MockKalshiClient, \
             patch('main.TradeExecutor'), \
             patch('main.PortfolioTracker'), \
             patch('main.TradeLogger'):
            app = MainApp()
            MockKalshiClient.assert_called_once_with()
            assert app.client is MockKalshiClient.return_value

    def test_init_creates_default_executor_with_shared_client(self):
        with patch('main.KalshiClient') as MockKalshiClient, \
             patch('main.TradeExecutor') as MockTradeExecutor, \
             patch('main.PortfolioTracker'), \
             patch('main.TradeLogger'):
            app = MainApp()
            MockTradeExecutor.assert_called_once_with(client=MockKalshiClient.return_value)
            assert app.executor is MockTradeExecutor.return_value

    def test_init_creates_default_tracker_with_shared_client(self):
        with patch('main.KalshiClient') as MockKalshiClient, \
             patch('main.TradeExecutor'), \
             patch('main.PortfolioTracker') as MockPortfolioTracker, \
             patch('main.TradeLogger'):
            app = MainApp()
            MockPortfolioTracker.assert_called_once_with(client=MockKalshiClient.return_value)
            assert app.tracker is MockPortfolioTracker.return_value

    def test_init_creates_default_logger(self):
        with patch('main.KalshiClient'), \
             patch('main.TradeExecutor'), \
             patch('main.PortfolioTracker'), \
             patch('main.TradeLogger') as MockTradeLogger:
            app = MainApp()
            MockTradeLogger.assert_called_once()
            assert app.logger is MockTradeLogger.return_value

    def test_init_accepts_injected_client(self):
        mock_client = Mock()
        with patch('main.TradeExecutor'), \
             patch('main.PortfolioTracker'), \
             patch('main.TradeLogger'):
            app = MainApp(client=mock_client)
            assert app.client is mock_client

    def test_init_accepts_all_injected_dependencies(self):
        mock_client = Mock()
        mock_executor = Mock()
        mock_tracker = Mock()
        mock_logger = Mock()
        app = MainApp(
            client=mock_client,
            executor=mock_executor,
            tracker=mock_tracker,
            logger=mock_logger,
        )
        assert app.client is mock_client
        assert app.executor is mock_executor
        assert app.tracker is mock_tracker
        assert app.logger is mock_logger

    def test_init_does_not_create_client_when_injected(self):
        mock_client = Mock()
        with patch('main.KalshiClient') as MockKalshiClient, \
             patch('main.TradeExecutor'), \
             patch('main.PortfolioTracker'), \
             patch('main.TradeLogger'):
            app = MainApp(client=mock_client)
            MockKalshiClient.assert_not_called()


# =============================================================================
# Group 2: Menu routing
# =============================================================================

class TestMainAppMenuRouting:

    def test_menu_choice_1_calls_view_portfolio(self, app):
        with patch("main.validate_config"), \
             patch("builtins.input", side_effect=["1", "6"]), \
             patch.object(app, "_view_portfolio") as mock_method:
            app.run()
            mock_method.assert_called_once()

    def test_menu_choice_2_calls_launch_trading(self, app):
        with patch("main.validate_config"), \
             patch("builtins.input", side_effect=["2", "6"]), \
             patch.object(app, "_launch_trading") as mock_method:
            app.run()
            mock_method.assert_called_once()

    def test_menu_choice_3_calls_view_open_orders(self, app):
        with patch("main.validate_config"), \
             patch("builtins.input", side_effect=["3", "6"]), \
             patch.object(app, "_view_open_orders") as mock_method:
            app.run()
            mock_method.assert_called_once()

    def test_menu_choice_4_calls_cancel_order(self, app):
        with patch("main.validate_config"), \
             patch("builtins.input", side_effect=["4", "6"]), \
             patch.object(app, "_cancel_order") as mock_method:
            app.run()
            mock_method.assert_called_once()

    def test_menu_choice_5_calls_view_trade_history(self, app):
        with patch("main.validate_config"), \
             patch("builtins.input", side_effect=["5", "6"]), \
             patch.object(app, "_view_trade_history") as mock_method:
            app.run()
            mock_method.assert_called_once()

    def test_menu_choice_6_exits_loop_without_calling_handlers(self, app):
        with patch("main.validate_config"), \
             patch("builtins.input", side_effect=["6"]), \
             patch.object(app, "_view_portfolio") as m1, \
             patch.object(app, "_launch_trading") as m2, \
             patch.object(app, "_view_open_orders") as m3, \
             patch.object(app, "_cancel_order") as m4, \
             patch.object(app, "_view_trade_history") as m5:
            app.run()
            m1.assert_not_called()
            m2.assert_not_called()
            m3.assert_not_called()
            m4.assert_not_called()
            m5.assert_not_called()

    def test_invalid_choice_prints_error_and_continues(self, app):
        with patch("main.validate_config"), \
             patch("builtins.input", side_effect=["invalid", "6"]), \
             patch("builtins.print") as mock_print:
            app.run()
            all_printed = " ".join(
                str(arg)
                for c in mock_print.call_args_list
                for arg in c.args
            ).lower()
            assert "invalid" in all_printed or "choice" in all_printed

    def test_multiple_valid_choices_all_routed(self, app):
        with patch("main.validate_config"), \
             patch("builtins.input", side_effect=["1", "3", "5", "6"]), \
             patch.object(app, "_view_portfolio") as m1, \
             patch.object(app, "_view_open_orders") as m3, \
             patch.object(app, "_view_trade_history") as m5:
            app.run()
            m1.assert_called_once()
            m3.assert_called_once()
            m5.assert_called_once()


# =============================================================================
# Group 3: _view_portfolio
# =============================================================================

class TestViewPortfolio:

    def test_view_portfolio_calls_display_portfolio_summary(self, app):
        app._view_portfolio()
        app.tracker.display_portfolio_summary.assert_called_once_with()

    def test_view_portfolio_returns_none_on_success(self, app):
        result = app._view_portfolio()
        assert result is None

    def test_view_portfolio_handles_portfolio_error_without_raising(self, app):
        app.tracker.display_portfolio_summary.side_effect = PortfolioError("fetch failed")
        with patch("builtins.print") as mock_print:
            app._view_portfolio()
            assert mock_print.called

    def test_view_portfolio_handles_unexpected_exception_without_raising(self, app):
        app.tracker.display_portfolio_summary.side_effect = RuntimeError("unexpected")
        with patch("builtins.print") as mock_print:
            app._view_portfolio()
            assert mock_print.called

    def test_view_portfolio_error_message_contains_useful_info(self, app):
        app.tracker.display_portfolio_summary.side_effect = PortfolioError("connection refused")
        printed_lines = []
        with patch("builtins.print", side_effect=lambda *args, **kw: printed_lines.append(" ".join(str(a) for a in args))):
            app._view_portfolio()
        assert printed_lines
        assert " ".join(printed_lines).strip() != ""


# =============================================================================
# Group 4: _view_open_orders
# =============================================================================

class TestViewOpenOrders:

    def test_view_open_orders_calls_list_open_orders(self, app):
        app.executor.list_open_orders.return_value = []
        app._view_open_orders()
        app.executor.list_open_orders.assert_called_once()

    def test_view_open_orders_empty_list_prints_no_orders_message(self, app):
        app.executor.list_open_orders.return_value = []
        with patch("builtins.print") as mock_print:
            app._view_open_orders()
        printed_text = " ".join(
            str(arg) for c in mock_print.call_args_list for arg in c.args
        ).lower()
        assert "no" in printed_text or "order" in printed_text

    def test_view_open_orders_calls_format_order_summary_for_each_order(self, app):
        app.executor.list_open_orders.return_value = [{"order_id": "abc"}, {"order_id": "def"}]
        with patch("main.format_order_summary", return_value="formatted") as mock_fmt:
            app._view_open_orders()
        assert mock_fmt.call_count == 2

    def test_view_open_orders_prints_each_formatted_order(self, app):
        app.executor.list_open_orders.return_value = [{"order_id": "abc"}]
        with patch("main.format_order_summary", return_value="ORDER_LINE"), \
             patch("builtins.print") as mock_print:
            app._view_open_orders()
        printed_args = [str(arg) for c in mock_print.call_args_list for arg in c.args]
        assert any("ORDER_LINE" in text for text in printed_args)

    def test_view_open_orders_handles_trade_execution_error_without_raising(self, app):
        app.executor.list_open_orders.side_effect = TradeExecutionError("API down")
        with patch("builtins.print") as mock_print:
            app._view_open_orders()
        assert mock_print.called

    def test_view_open_orders_returns_none(self, app):
        app.executor.list_open_orders.return_value = []
        assert app._view_open_orders() is None


# =============================================================================
# Group 5: _cancel_order
# =============================================================================

class TestCancelOrder:

    def test_cancel_order_calls_executor_cancel_with_order_id(self, app):
        with patch("builtins.input", return_value="order-123"), \
             patch("main.confirm", return_value=True):
            app.executor.cancel_order.return_value = {"order": {"status": "cancelled"}}
            app._cancel_order()
            app.executor.cancel_order.assert_called_once_with("order-123")

    def test_cancel_order_prints_success_message(self, app):
        with patch("builtins.input", return_value="order-123"), \
             patch("main.confirm", return_value=True), \
             patch("builtins.print") as mock_print:
            app.executor.cancel_order.return_value = {"status": "cancelled"}
            app._cancel_order()
            printed_text = " ".join(
                str(arg) for c in mock_print.call_args_list for arg in c.args
            ).lower()
            assert any(w in printed_text for w in ("cancel", "success", "cancelled"))

    def test_cancel_order_empty_input_returns_early_without_calling_cancel(self, app):
        with patch("builtins.input", return_value=""):
            app._cancel_order()
            app.executor.cancel_order.assert_not_called()

    def test_cancel_order_user_declines_confirmation_does_not_cancel(self, app):
        with patch("builtins.input", return_value="order-456"), \
             patch("main.confirm", return_value=False):
            app._cancel_order()
            app.executor.cancel_order.assert_not_called()

    def test_cancel_order_handles_trade_execution_error_without_raising(self, app):
        with patch("builtins.input", return_value="order-789"), \
             patch("main.confirm", return_value=True), \
             patch("builtins.print") as mock_print:
            app.executor.cancel_order.side_effect = TradeExecutionError("not found")
            app._cancel_order()
            printed_text = " ".join(
                str(arg) for c in mock_print.call_args_list for arg in c.args
            ).lower()
            assert any(w in printed_text for w in ("error", "not found", "failed", "cancel"))

    def test_cancel_order_whitespace_only_input_returns_early(self, app):
        with patch("builtins.input", return_value="   "):
            app._cancel_order()
            app.executor.cancel_order.assert_not_called()

    def test_cancel_order_returns_none(self, app):
        with patch("builtins.input", return_value="order-123"), \
             patch("main.confirm", return_value=True):
            app.executor.cancel_order.return_value = {"status": "cancelled"}
            assert app._cancel_order() is None


# =============================================================================
# Group 6: _view_trade_history
# =============================================================================

class TestViewTradeHistory:

    def test_view_trade_history_calls_display_recent_trades(self, app):
        app._view_trade_history()
        app.logger.display_recent_trades.assert_called_once()

    def test_view_trade_history_returns_none_on_success(self, app):
        assert app._view_trade_history() is None

    def test_view_trade_history_handles_exception_without_raising(self, app):
        app.logger.display_recent_trades.side_effect = RuntimeError("log corrupted")
        try:
            app._view_trade_history()
        except Exception:
            pytest.fail("_view_trade_history() raised an exception unexpectedly")

    def test_view_trade_history_prints_error_message_on_exception(self, app):
        app.logger.display_recent_trades.side_effect = Exception("failed")
        with patch("builtins.print") as mock_print:
            app._view_trade_history()
            mock_print.assert_called()

    def test_view_trade_history_does_not_call_other_dependencies(self, app):
        app._view_trade_history()
        app.executor.list_open_orders.assert_not_called()
        app.tracker.display_portfolio_summary.assert_not_called()


# =============================================================================
# Group 7: Shutdown and entry point
# =============================================================================

class TestShutdownAndEntryPoint:

    def test_run_returns_cleanly_on_config_error(self, app):
        with patch('main.validate_config',
                   side_effect=ConfigurationError("missing KALSHI_API_KEY")):
            app.run()  # must not raise

    def test_run_prints_error_message_on_config_error(self, app):
        with patch('main.validate_config',
                   side_effect=ConfigurationError("missing KALSHI_API_KEY")), \
             patch('builtins.print') as mock_print:
            app.run()
        assert mock_print.called

    def test_run_does_not_enter_menu_loop_on_config_error(self, app):
        with patch('main.validate_config',
                   side_effect=ConfigurationError("bad config")), \
             patch('builtins.input') as mock_input:
            app.run()
        mock_input.assert_not_called()

    def test_run_handles_keyboard_interrupt_without_raising(self, app):
        with patch('main.validate_config'), \
             patch('builtins.input', side_effect=KeyboardInterrupt()):
            app.run()  # must not raise

    def test_run_prints_goodbye_on_keyboard_interrupt(self, app):
        with patch('main.validate_config'), \
             patch('builtins.input', side_effect=KeyboardInterrupt()), \
             patch('builtins.print') as mock_print:
            app.run()
        assert mock_print.called

    def test_main_function_creates_main_app_and_calls_run(self):
        with patch('main.MainApp') as MockMainApp:
            run_main()
        MockMainApp.assert_called_once()
        MockMainApp.return_value.run.assert_called_once()

    def test_main_function_handles_keyboard_interrupt_gracefully(self):
        with patch('main.MainApp') as MockMainApp:
            MockMainApp.return_value.run.side_effect = KeyboardInterrupt()
            run_main()  # must not raise
