# cli_interface.py - CLI interface (Task 2)
"""
Command-line interface for the Kalshi Trading System.

Provides an interactive menu-driven interface for placing trades,
viewing orders, and managing positions.
"""

from trade_executor import TradeExecutor, TradeExecutionError
from trade_logger import TradeLogger


def format_price_dollars(cents: int) -> str:
    """Convert cents to dollar string."""
    return f"${cents / 100:.2f}"


def format_order_summary(order: dict) -> str:
    """Format an order dict for display."""
    order_data = order.get("order", order)
    order_id = order_data.get("order_id", "N/A")
    ticker = order_data.get("ticker", "N/A")
    side = order_data.get("side", "N/A")
    action = order_data.get("action", "N/A")
    status = order_data.get("status", "N/A")
    count = order_data.get("remaining_count", order_data.get("count", 0))

    price = order_data.get("yes_price") or order_data.get("no_price")
    price_str = f"{price}c" if price else "market"

    return f"  {order_id[:12]}...  {action.upper()} {count} {side.upper()} @ {price_str}  [{status}]  {ticker}"


def print_header(title: str) -> None:
    """Print a section header."""
    print(f"\n{'='*50}")
    print(f"  {title}")
    print(f"{'='*50}")


def print_market_info(market: dict) -> None:
    """Display market information."""
    print(f"\n  Market: {market.get('ticker', 'N/A')}")
    print(f"  Title:  {market.get('title', 'N/A')}")
    print(f"  Status: {market.get('status', 'N/A')}")

    yes_bid = market.get("yes_bid")
    yes_ask = market.get("yes_ask")
    if yes_bid is not None and yes_ask is not None:
        print(f"  YES:    {yes_bid}c bid / {yes_ask}c ask")
        print(f"  NO:     {100 - yes_ask}c bid / {100 - yes_bid}c ask")
    print()


def get_input(prompt: str, validator=None, error_msg: str = "Invalid input") -> str:
    """Get validated input from user."""
    while True:
        value = input(prompt).strip()
        if validator is None or validator(value):
            return value
        print(f"  Error: {error_msg}")


def get_int_input(prompt: str, min_val: int = None, max_val: int = None) -> int:
    """Get integer input with optional bounds."""
    while True:
        value = input(prompt).strip()
        try:
            num = int(value)
            if min_val is not None and num < min_val:
                print(f"  Error: Must be at least {min_val}")
                continue
            if max_val is not None and num > max_val:
                print(f"  Error: Must be at most {max_val}")
                continue
            return num
        except ValueError:
            print("  Error: Please enter a valid number")


def confirm(prompt: str) -> bool:
    """Ask for yes/no confirmation."""
    response = input(f"{prompt} (yes/no): ").strip().lower()
    return response in ("yes", "y")


class TradingCLI:
    """Interactive command-line interface for trading."""

    def __init__(self, logger: TradeLogger = None):
        """Initialize the CLI with a trade executor."""
        self.executor = None
        self.logger = logger

    def _ensure_executor(self) -> bool:
        """Ensure executor is initialized. Returns False if initialization fails."""
        if self.executor is None:
            try:
                print("\n  Connecting to Kalshi API...")
                self.executor = TradeExecutor()
                print("  Connected successfully.")
                return True
            except Exception as e:
                print(f"\n  Error: Failed to connect to Kalshi API: {e}")
                return False
        return True

    def run(self) -> None:
        """Run the trading CLI main loop."""
        print_header("Kalshi Trading Interface")

        while True:
            self._show_menu()
            choice = input("\n  Enter choice (1-7): ").strip()

            if choice == "1":
                self._search_markets()
            elif choice == "2":
                self._place_market_order()
            elif choice == "3":
                self._place_limit_order()
            elif choice == "4":
                self._view_open_orders()
            elif choice == "5":
                self._cancel_order()
            elif choice == "6":
                self._check_order_status()
            elif choice == "7":
                print("\n  Goodbye!")
                break
            else:
                print("  Invalid choice. Please enter 1-7.")

    def _show_menu(self) -> None:
        """Display the main menu."""
        print("\n  -------------------------")
        print("  1. Search markets")
        print("  2. Place market order")
        print("  3. Place limit order")
        print("  4. View open orders")
        print("  5. Cancel an order")
        print("  6. Check order status")
        print("  7. Exit")
        print("  -------------------------")

    def _search_markets(self) -> None:
        """Search and browse available markets."""
        print_header("Search Markets")

        if not self._ensure_executor():
            return

        # Get search query (optional)
        query = input("  Search term (or press Enter to browse all): ").strip()

        # Get status filter
        print("\n  Filter by status:")
        print("    1. Active/open markets only (default)")
        print("    2. All markets")
        print("    3. Closed markets")
        status_choice = input("  Choice (1-3): ").strip()

        if status_choice == "2":
            status = None
        elif status_choice == "3":
            status = "closed"
        else:
            status = "open"

        try:
            markets = self.executor.search_markets(
                query=query if query else None,
                status=status,
                limit=50
            )

            # If no results and user provided a query, offer to search by series
            if not markets and query:
                print("\n  No markets found in popular series.")
                print("  You can try searching a specific series (e.g., KXFIRSTSUPERBOWLSONG).")
                print("  Find series names on kalshi.com by looking at market ticker prefixes.")
                series = input("\n  Enter series ticker (or press Enter to skip): ").strip().upper()

                if series:
                    markets = self.executor.search_markets(
                        query=query,
                        status=status,
                        series_ticker=series,
                        limit=50
                    )

            if not markets:
                print("\n  No markets found matching your criteria.")
                return

            print(f"\n  Found {len(markets)} market(s):\n")

            for market in markets:
                ticker = market.get("ticker", "N/A")
                title = market.get("title", "N/A")
                status_str = market.get("status", "N/A")
                yes_bid = market.get("yes_bid", 0)
                yes_ask = market.get("yes_ask", 0)
                volume = market.get("volume_24h", 0)

                print(f"  {ticker}")
                print(f"    {title[:70]}")
                if yes_bid or yes_ask:
                    print(f"    YES: {yes_bid}c bid / {yes_ask}c ask  |  Status: {status_str}  |  24h Vol: {volume}")
                else:
                    print(f"    Status: {status_str}  |  24h Vol: {volume}")
                print()

            print("  Tip: Copy a ticker from above to use when placing orders.")
            print()

        except TradeExecutionError as e:
            print(f"\n  Error: {e}")

    def _place_market_order(self) -> None:
        """Handle placing a market order."""
        print_header("Place Market Order")

        if not self._ensure_executor():
            return

        # Get ticker and validate
        ticker = input("  Enter market ticker: ").strip().upper()
        if not ticker:
            print("  Cancelled.")
            return

        try:
            market = self.executor.get_market_info(ticker)
            print_market_info(market)

            if market.get("status") not in ("active", "open"):
                print("  Error: This market is not open for trading.")
                return
        except TradeExecutionError as e:
            print(f"  Error: {e}")
            return

        # Get side
        side = input("  Enter side (yes/no): ").strip().lower()
        if side not in ("yes", "no"):
            print("  Error: Side must be 'yes' or 'no'")
            return

        # Get quantity
        try:
            quantity = get_int_input("  Enter quantity: ", min_val=1)
        except (KeyboardInterrupt, EOFError):
            print("\n  Cancelled.")
            return

        # Confirm order
        print("\n  Order Summary:")
        print(f"    Market:   {ticker}")
        print(f"    Side:     {side.upper()}")
        print(f"    Quantity: {quantity}")
        print(f"    Type:     MARKET")
        print()

        if not confirm("  Confirm order?"):
            print("  Order cancelled.")
            return

        # Place order
        try:
            result = self.executor.place_market_order(ticker, side, quantity)
            order = result.get("order", result)
            print(f"\n  Order placed successfully!")
            print(f"  Order ID: {order.get('order_id', 'N/A')}")
            print(f"  Status:   {order.get('status', 'N/A')}")
            if self.logger is not None:
                try:
                    self.logger.log_order_submission(result)
                except Exception:
                    pass
        except TradeExecutionError as e:
            print(f"\n  Error: {e}")

    def _place_limit_order(self) -> None:
        """Handle placing a limit order."""
        print_header("Place Limit Order")

        if not self._ensure_executor():
            return

        # Get ticker and validate
        ticker = input("  Enter market ticker: ").strip().upper()
        if not ticker:
            print("  Cancelled.")
            return

        try:
            market = self.executor.get_market_info(ticker)
            print_market_info(market)

            if market.get("status") not in ("active", "open"):
                print("  Error: This market is not open for trading.")
                return
        except TradeExecutionError as e:
            print(f"  Error: {e}")
            return

        # Get side
        side = input("  Enter side (yes/no): ").strip().lower()
        if side not in ("yes", "no"):
            print("  Error: Side must be 'yes' or 'no'")
            return

        # Get quantity
        try:
            quantity = get_int_input("  Enter quantity: ", min_val=1)
        except (KeyboardInterrupt, EOFError):
            print("\n  Cancelled.")
            return

        # Get price
        try:
            price = get_int_input("  Enter price in cents (1-99): ", min_val=1, max_val=99)
        except (KeyboardInterrupt, EOFError):
            print("\n  Cancelled.")
            return

        # Confirm order
        print("\n  Order Summary:")
        print(f"    Market:   {ticker}")
        print(f"    Side:     {side.upper()}")
        print(f"    Quantity: {quantity}")
        print(f"    Price:    {price}c ({format_price_dollars(price)})")
        print(f"    Type:     LIMIT")
        print(f"    Cost:     {format_price_dollars(price * quantity)} (max)")
        print()

        if not confirm("  Confirm order?"):
            print("  Order cancelled.")
            return

        # Place order
        try:
            result = self.executor.place_limit_order(ticker, side, quantity, price)
            order = result.get("order", result)
            print(f"\n  Order placed successfully!")
            print(f"  Order ID: {order.get('order_id', 'N/A')}")
            print(f"  Status:   {order.get('status', 'N/A')}")
            if self.logger is not None:
                try:
                    self.logger.log_order_submission(result)
                except Exception:
                    pass
        except TradeExecutionError as e:
            print(f"\n  Error: {e}")

    def _view_open_orders(self) -> None:
        """Display all open orders."""
        print_header("Open Orders")

        if not self._ensure_executor():
            return

        try:
            orders = self.executor.list_open_orders()

            if not orders:
                print("\n  No open orders.")
                return

            print(f"\n  Found {len(orders)} open order(s):\n")
            for order in orders:
                print(format_order_summary(order))
            print()
        except TradeExecutionError as e:
            print(f"\n  Error: {e}")

    def _cancel_order(self) -> None:
        """Handle cancelling an order."""
        print_header("Cancel Order")

        if not self._ensure_executor():
            return

        # Show open orders first
        try:
            orders = self.executor.list_open_orders()
            if orders:
                print("\n  Current open orders:")
                for order in orders:
                    print(format_order_summary(order))
                print()
        except TradeExecutionError:
            pass  # Continue even if we can't list orders

        order_id = input("  Enter order ID to cancel: ").strip()
        if not order_id:
            print("  Cancelled.")
            return

        if not confirm(f"  Cancel order {order_id[:20]}...?"):
            print("  Cancelled.")
            return

        try:
            result = self.executor.cancel_order(order_id)
            order = result.get("order", result)
            print(f"\n  Order cancelled successfully!")
            print(f"  Status: {order.get('status', 'cancelled')}")
            if self.logger is not None:
                try:
                    self.logger.log_order_cancellation(order_id)
                except Exception:
                    pass
        except TradeExecutionError as e:
            print(f"\n  Error: {e}")

    def _check_order_status(self) -> None:
        """Check the status of a specific order."""
        print_header("Check Order Status")

        if not self._ensure_executor():
            return

        order_id = input("  Enter order ID: ").strip()
        if not order_id:
            print("  Cancelled.")
            return

        try:
            result = self.executor.get_order_status(order_id)
            order = result.get("order", result)

            print(f"\n  Order Details:")
            print(f"    Order ID:  {order.get('order_id', 'N/A')}")
            print(f"    Ticker:    {order.get('ticker', 'N/A')}")
            print(f"    Side:      {order.get('side', 'N/A').upper()}")
            print(f"    Action:    {order.get('action', 'N/A').upper()}")
            print(f"    Status:    {order.get('status', 'N/A')}")
            print(f"    Quantity:  {order.get('count', 'N/A')}")
            print(f"    Remaining: {order.get('remaining_count', 'N/A')}")

            price = order.get("yes_price") or order.get("no_price")
            if price:
                print(f"    Price:     {price}c")

            print()
        except TradeExecutionError as e:
            print(f"\n  Error: {e}")


def run_trading_cli() -> None:
    """Entry point for the trading CLI."""
    cli = TradingCLI()
    try:
        cli.run()
    except KeyboardInterrupt:
        print("\n\n  Interrupted. Goodbye!")
    except Exception as e:
        print(f"\n  Unexpected error: {e}")


if __name__ == "__main__":
    run_trading_cli()
