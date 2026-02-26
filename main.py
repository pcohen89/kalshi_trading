"""
Main entry point for the Kalshi Trading System.

Provides a top-level menu that routes the user to portfolio viewing,
trade execution, order management, and trade history. All sub-operations
delegate to dedicated modules; this module is responsible only for startup
validation, navigation, and graceful error handling.
"""

from config import ConfigurationError, validate_config
from kalshi_client import KalshiClient
from trade_executor import TradeExecutor, TradeExecutionError
from portfolio_tracker import PortfolioTracker, PortfolioError
from trade_logger import TradeLogger
from cli_interface import TradingCLI, confirm, format_order_summary


class MainApp:
    """Top-level application controller for the Kalshi Trading System."""

    def __init__(
        self,
        client: KalshiClient = None,
        executor: TradeExecutor = None,
        tracker: PortfolioTracker = None,
        logger: TradeLogger = None,
    ) -> None:
        """
        Initialise the application with optional dependency injection.

        When a dependency is not provided, a default instance is created
        internally. Injecting dependencies enables unit testing without
        touching real APIs or the filesystem.
        """
        self.client: KalshiClient = client if client is not None else KalshiClient()
        self.executor: TradeExecutor = (
            executor if executor is not None else TradeExecutor(client=self.client)
        )
        self.tracker: PortfolioTracker = (
            tracker if tracker is not None else PortfolioTracker(client=self.client)
        )
        self.logger: TradeLogger = logger if logger is not None else TradeLogger()

    def run(self) -> None:
        """Validate configuration, then enter the interactive main menu loop."""
        try:
            validate_config()
        except ConfigurationError as exc:
            print(f"\n  Configuration error: {exc}")
            print("  Please check your API credentials and configuration, then try again.")
            return

        print(f"\n{'='*50}")
        print("  Kalshi Trading System")
        print(f"{'='*50}")

        try:
            while True:
                self._show_menu()
                choice = input("\n  Enter choice (1-6): ").strip()

                if choice == "1":
                    self._view_portfolio()
                elif choice == "2":
                    self._launch_trading()
                elif choice == "3":
                    self._view_open_orders()
                elif choice == "4":
                    self._cancel_order()
                elif choice == "5":
                    self._view_trade_history()
                elif choice == "6":
                    print("\n  Goodbye!")
                    break
                else:
                    print("  Invalid choice. Please enter 1-6.")
        except KeyboardInterrupt:
            print("\n\n  Goodbye!")

    def _show_menu(self) -> None:
        """Print the main navigation menu."""
        print("\n  -------------------------")
        print("  1. View portfolio summary")
        print("  2. Place a trade")
        print("  3. View open orders")
        print("  4. Cancel an order")
        print("  5. View recent trade history")
        print("  6. Exit")
        print("  -------------------------")

    def _view_portfolio(self) -> None:
        """Display the portfolio summary, catching any portfolio errors."""
        try:
            self.tracker.display_portfolio_summary()
        except PortfolioError as exc:
            print(f"\n  Portfolio error: {exc}")
        except Exception as exc:
            print(f"\n  Unexpected error displaying portfolio: {exc}")

    def _launch_trading(self) -> None:
        """Launch the interactive trading sub-menu."""
        try:
            cli = TradingCLI(logger=self.logger)
            cli.run()
        except Exception as exc:
            print(f"\n  Error in trading interface: {exc}")

    def _view_open_orders(self) -> None:
        """Fetch and display all open orders."""
        try:
            orders = self.executor.list_open_orders()
            if not orders:
                print("\n  No open orders.")
                return
            print(f"\n  Found {len(orders)} open order(s):\n")
            for order in orders:
                print(format_order_summary(order))
            print()
        except TradeExecutionError as exc:
            print(f"\n  Trade execution error: {exc}")

    def _cancel_order(self) -> None:
        """Prompt the user for an order ID and cancel it after confirmation."""
        order_id = input("\n  Enter order ID to cancel: ").strip()
        if not order_id:
            print("  Cancelled.")
            return

        if not confirm(f"  Cancel order {order_id[:20]}...?"):
            print("  Cancelled.")
            return

        try:
            result = self.executor.cancel_order(order_id)
            order = result.get("order", result)
            status = order.get("status", "cancelled")
            print(f"\n  Order cancelled successfully! Status: {status}")
        except TradeExecutionError as exc:
            print(f"\n  Trade execution error: {exc}")

    def _view_trade_history(self) -> None:
        """Display recent trade history from the trade log."""
        try:
            self.logger.display_recent_trades()
        except Exception as exc:
            print(f"\n  Error displaying trade history: {exc}")


def main() -> None:
    """Create and run the main application."""
    app = MainApp()
    try:
        app.run()
    except KeyboardInterrupt:
        print("\n\nGoodbye!")


if __name__ == "__main__":
    main()
