# trade_executor.py - Order execution wrapper (Task 2)
"""
Trade execution functions for the Kalshi Trading System.

Provides simplified wrapper functions around KalshiClient for common
trading operations with additional validation and error handling.
"""

import logging
from typing import Optional

from kalshi_client import KalshiClient, KalshiAPIError


logger = logging.getLogger(__name__)


class TradeExecutionError(Exception):
    """Exception raised for trade execution errors."""
    pass


class TradeExecutor:
    """
    Wrapper for common trading operations.

    Usage:
        executor = TradeExecutor()
        order = executor.place_market_order("TICKER-YES", "yes", 10)
    """

    def __init__(self, client: Optional[KalshiClient] = None):
        """
        Initialize the trade executor.

        Args:
            client: Optional KalshiClient instance. Creates one if not provided.
        """
        self.client = client or KalshiClient()

    def place_market_order(self, ticker: str, side: str, quantity: int) -> dict:
        """
        Place a market order.

        Args:
            ticker: Market ticker
            side: "yes" or "no"
            quantity: Number of contracts (positive integer)

        Returns:
            dict with order details including order_id

        Raises:
            TradeExecutionError: If validation fails or order placement fails
        """
        self._validate_side(side)
        self._validate_quantity(quantity)

        try:
            result = self.client.place_order(
                ticker=ticker,
                side=side,
                quantity=quantity,
                action="buy",
                order_type="market"
            )
            logger.info("Market order placed: %s %s %d @ market", side, ticker, quantity)
            return result
        except KalshiAPIError as e:
            logger.error("Failed to place market order: %s", e)
            raise TradeExecutionError(f"Failed to place market order: {e}")

    def place_limit_order(self, ticker: str, side: str, quantity: int, price: int) -> dict:
        """
        Place a limit order.

        Args:
            ticker: Market ticker
            side: "yes" or "no"
            quantity: Number of contracts (positive integer)
            price: Price in cents (1-99)

        Returns:
            dict with order details including order_id

        Raises:
            TradeExecutionError: If validation fails or order placement fails
        """
        self._validate_side(side)
        self._validate_quantity(quantity)
        self._validate_price(price)

        try:
            result = self.client.place_order(
                ticker=ticker,
                side=side,
                quantity=quantity,
                action="buy",
                order_type="limit",
                price=price
            )
            logger.info("Limit order placed: %s %s %d @ %d¢", side, ticker, quantity, price)
            return result
        except KalshiAPIError as e:
            logger.error("Failed to place limit order: %s", e)
            raise TradeExecutionError(f"Failed to place limit order: {e}")

    def cancel_order(self, order_id: str) -> dict:
        """
        Cancel a pending order.

        Args:
            order_id: The order ID to cancel

        Returns:
            dict with cancelled order details

        Raises:
            TradeExecutionError: If cancellation fails
        """
        if not order_id or not order_id.strip():
            raise TradeExecutionError("Order ID cannot be empty")

        try:
            result = self.client.cancel_order(order_id)
            logger.info("Order cancelled: %s", order_id)
            return result
        except KalshiAPIError as e:
            logger.error("Failed to cancel order %s: %s", order_id, e)
            raise TradeExecutionError(f"Failed to cancel order: {e}")

    def get_order_status(self, order_id: str) -> dict:
        """
        Get the status of an order.

        Args:
            order_id: The order ID to check

        Returns:
            dict with order details including status

        Raises:
            TradeExecutionError: If order lookup fails
        """
        if not order_id or not order_id.strip():
            raise TradeExecutionError("Order ID cannot be empty")

        try:
            return self.client.get_order(order_id)
        except KalshiAPIError as e:
            logger.error("Failed to get order status for %s: %s", order_id, e)
            raise TradeExecutionError(f"Failed to get order status: {e}")

    def list_open_orders(self) -> list:
        """
        Get all open (resting) orders.

        Returns:
            List of order objects with status "resting"
        """
        try:
            result = self.client.get_orders(status="resting")
            return result.get("orders", [])
        except KalshiAPIError as e:
            logger.error("Failed to list open orders: %s", e)
            raise TradeExecutionError(f"Failed to list open orders: {e}")

    def get_market_info(self, ticker: str) -> dict:
        """
        Get information about a market.

        Args:
            ticker: Market ticker

        Returns:
            dict with market details

        Raises:
            TradeExecutionError: If market lookup fails
        """
        if not ticker or not ticker.strip():
            raise TradeExecutionError("Ticker cannot be empty")

        try:
            result = self.client.get_market(ticker)
            return result.get("market", result)
        except KalshiAPIError as e:
            logger.error("Failed to get market info for %s: %s", ticker, e)
            raise TradeExecutionError(f"Failed to get market info: {e}")

    def validate_ticker(self, ticker: str) -> bool:
        """
        Check if a ticker exists and the market is active/open.

        Args:
            ticker: Market ticker to validate

        Returns:
            True if ticker exists and market is active, False otherwise
        """
        try:
            market = self.get_market_info(ticker)
            # Kalshi API uses "active" for open markets
            return market.get("status") in ("active", "open")
        except TradeExecutionError:
            return False

    # Popular series on Kalshi (searched in order)
    POPULAR_SERIES = [
        # Crypto
        "KXBTC",      # Bitcoin price
        "KXETH",      # Ethereum price
        # Financial / Economic
        "INXD",       # S&P 500 / indexes
        "KXFED",      # Federal Reserve
        "KXCPI",      # Inflation / CPI
        "KXGDP",      # GDP
        "KXJOBS",     # Jobs / employment
        "KXRATE",     # Interest rates
        # Politics
        "PRES",       # Presidential / politics
        "KXELECT",    # Elections
        # Sports
        "KXNBA",      # NBA
        "KXNFL",      # NFL
        "KXMLB",      # MLB
        "KXNHL",      # NHL
        "KXSOCCER",   # Soccer
        "KXNCAAMB",   # NCAA basketball
        # Entertainment / Events
        "KXFIRSTSUPERBOWLSONG",  # Super Bowl halftime
        "KXSUPERBOWL",           # Super Bowl
        "KXOSCARS",              # Oscars
        "KXGRAMMYS",             # Grammys
        "KXEMMYS",               # Emmys
    ]

    def search_markets(
        self,
        query: str = None,
        status: str = "open",
        limit: int = 20,
        series_ticker: str = None
    ) -> list:
        """
        Search for markets.

        Args:
            query: Optional search term to filter by title (case-insensitive)
            status: Market status filter ("open", "closed", "settled", or None for all)
                    Note: API uses "open" for filter but returns "active" in response
            limit: Maximum number of results to return
            series_ticker: Optional series ticker to filter by category

        Returns:
            List of market dicts matching the criteria
        """
        try:
            # If searching with query, search across popular series
            if query:
                query_lower = query.lower()
                matches = []
                seen_tickers = set()  # Track seen tickers to avoid duplicates

                # If specific series provided, only search that
                series_to_search = [series_ticker] if series_ticker else self.POPULAR_SERIES

                for series in series_to_search:
                    try:
                        result = self.client.get_markets(
                            limit=100, status=status, series_ticker=series
                        )
                        markets = result.get("markets", [])

                        # Filter by query and deduplicate
                        for m in markets:
                            ticker = m.get("ticker")
                            if ticker in seen_tickers:
                                continue
                            if (query_lower in m.get("title", "").lower()
                                    or query_lower in m.get("ticker", "").lower()):
                                matches.append(m)
                                seen_tickers.add(ticker)

                        # Exit early if we found enough matches
                        if len(matches) >= limit:
                            return matches[:limit]

                    except KalshiAPIError:
                        pass  # Skip if series doesn't exist

                # Fallback: search without series filter if no matches found
                if not matches and not series_ticker:
                    cursor = None
                    for _ in range(3):  # Check up to 300 markets
                        result = self.client.get_markets(
                            limit=100, status=status, cursor=cursor
                        )
                        markets = result.get("markets", [])
                        for m in markets:
                            ticker = m.get("ticker")
                            if ticker in seen_tickers:
                                continue
                            if (query_lower in m.get("title", "").lower()
                                    or query_lower in m.get("ticker", "").lower()):
                                matches.append(m)
                                seen_tickers.add(ticker)
                        cursor = result.get("cursor")
                        if not cursor or len(matches) >= limit:
                            break

                return matches[:limit]
            else:
                # No query - just return first batch from specified or default series
                result = self.client.get_markets(
                    limit=limit, status=status, series_ticker=series_ticker
                )
                return result.get("markets", [])

        except KalshiAPIError as e:
            logger.error("Failed to search markets: %s", e)
            raise TradeExecutionError(f"Failed to search markets: {e}")

    def _validate_side(self, side: str) -> None:
        """Validate order side."""
        if side not in ("yes", "no"):
            raise TradeExecutionError("Side must be 'yes' or 'no'")

    def _validate_quantity(self, quantity: int) -> None:
        """Validate order quantity."""
        if not isinstance(quantity, int) or quantity <= 0:
            raise TradeExecutionError("Quantity must be a positive integer")

    def _validate_price(self, price: int) -> None:
        """Validate limit order price."""
        if price is None:
            raise TradeExecutionError("Price is required for limit orders")
        if not isinstance(price, int) or price < 1 or price > 99:
            raise TradeExecutionError("Price must be an integer between 1 and 99 cents")
