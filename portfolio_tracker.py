# portfolio_tracker.py - Position tracking (Task 3)
"""
Portfolio and position tracking for the Kalshi Trading System.

Provides real-time portfolio visibility including:
- Open position listing with current market prices
- Unrealized P&L calculation (mark-to-market)
- Realized P&L aggregation from settled positions
- Formatted portfolio summary display
"""

import logging
from typing import Optional

from kalshi_client import KalshiClient, KalshiAPIError


logger = logging.getLogger(__name__)


# =============================================================================
# Helper Functions
# =============================================================================

def _format_dollars(cents: Optional[int]) -> str:
    """
    Format cents as a dollar string.

    Args:
        cents: Amount in cents (e.g. 1234)

    Returns:
        Formatted string (e.g. "$12.34")
    """
    if cents is None:
        return "$0.00"
    return f"${abs(cents) / 100:.2f}"


def _format_pnl(cents: Optional[int]) -> str:
    """
    Format cents as a signed P&L dollar string.

    Args:
        cents: P&L amount in cents (positive = profit, negative = loss)

    Returns:
        Formatted string (e.g. "+$5.00" or "-$3.00")
    """
    if cents is None:
        return "+$0.00"
    if cents >= 0:
        return f"+${cents / 100:.2f}"
    else:
        return f"-${abs(cents) / 100:.2f}"


def _print_position_line(pos: dict) -> None:
    """
    Print a formatted single position line.

    Args:
        pos: Position dict with ticker, title, quantity, side, cost, value, pnl, etc.
    """
    ticker = pos.get("ticker", "UNKNOWN")
    title = pos.get("title", "")
    quantity = pos.get("quantity", 0)
    side = pos.get("side", "yes").upper()
    avg_price = pos.get("avg_price", 0)
    cost = pos.get("cost", 0)
    value = pos.get("value", 0)
    pnl = pos.get("pnl", 0)
    status = pos.get("status", "unknown")

    # Calculate percentage return
    pnl_pct = (pnl / cost * 100) if cost else 0.0

    print(f"  {ticker}")
    if title:
        print(f"    {title}")
    print(f"    {quantity} {side} @ {avg_price}c  |  Cost: {_format_dollars(cost)}  |  Value: {_format_dollars(value)}")
    print(f"    P&L: {_format_pnl(pnl)} ({pnl_pct:+.1f}%)  |  Status: {status}")


# =============================================================================
# Exception
# =============================================================================

class PortfolioError(Exception):
    """Exception raised for portfolio tracking errors."""
    pass


# =============================================================================
# Portfolio Tracker
# =============================================================================

class PortfolioTracker:
    """
    Tracks portfolio positions and calculates P&L.

    Usage:
        tracker = PortfolioTracker()
        positions = tracker.get_current_positions()
        tracker.display_portfolio_summary()
    """

    # Maximum pages to fetch to prevent infinite loops
    MAX_PAGES = 50

    def __init__(self, client: Optional[KalshiClient] = None):
        """
        Initialize the portfolio tracker.

        Args:
            client: Optional KalshiClient instance. Creates one if not provided.
        """
        self.client = client or KalshiClient()

    # -------------------------------------------------------------------------
    # Internal Fetchers
    # -------------------------------------------------------------------------

    def _paginate(self, fetch_method, result_keys: list, error_label: str) -> list:
        """
        Generic pagination helper for Kalshi list endpoints.

        Args:
            fetch_method: Client method to call (e.g. self.client.get_positions).
                Must accept limit and cursor keyword arguments.
            result_keys: List of possible keys to extract items from the response.
                The first key that returns a truthy value is used.
            error_label: Human-readable label for error messages (e.g. "positions").

        Returns:
            List of all items across all pages.

        Raises:
            PortfolioError: If the API call fails.
        """
        all_items = []
        cursor = None

        try:
            for _ in range(self.MAX_PAGES):
                result = fetch_method(limit=100, cursor=cursor)

                # Try each possible key; fall back to empty list
                items = None
                for key in result_keys:
                    items = result.get(key)
                    if items:
                        break
                if not items:
                    break

                all_items.extend(items)

                cursor = result.get("cursor")
                if not cursor:
                    break

            return all_items
        except KalshiAPIError as e:
            logger.error("Failed to fetch %s: %s", error_label, e)
            raise PortfolioError(f"Failed to fetch {error_label}: {e}")

    def _fetch_all_positions(self) -> list:
        """Fetch all positions with pagination."""
        return self._paginate(self.client.get_positions, ["market_positions", "positions"], "positions")

    def _fetch_all_fills(self) -> list:
        """Fetch all fills with pagination."""
        return self._paginate(self.client.get_fills, ["fills"], "fills")

    def _fetch_all_settlements(self) -> list:
        """Fetch all settlements with pagination."""
        return self._paginate(self.client.get_settlements, ["settlements"], "settlements")

    def _get_market_price(self, ticker: str) -> dict:
        """
        Get current pricing for a market.

        Args:
            ticker: Market ticker.

        Returns:
            dict with keys: yes_bid, yes_ask, yes_price, last_price, status,
            title, result (if settled).

        Raises:
            PortfolioError: If the API call fails.
        """
        try:
            result = self.client.get_market(ticker)
            market = result.get("market", result)
            return {
                "yes_bid": market.get("yes_bid", 0),
                "yes_ask": market.get("yes_ask", 0),
                "yes_price": market.get("yes_price", 0),
                "last_price": market.get("last_price", 0),
                "status": market.get("status", "unknown"),
                "title": market.get("title", ""),
                "result": market.get("result", ""),
            }
        except KalshiAPIError as e:
            logger.error("Failed to get market price for %s: %s", ticker, e)
            raise PortfolioError(f"Failed to get market price for {ticker}: {e}")

    def _compute_fill_based_realized_pnl(self) -> dict:
        """
        Compute realized P&L from fill data using FIFO matching.

        Fetches all fills and groups them by (ticker, side). For each group
        that has sell fills, matches buys to sells in FIFO order and computes
        the P&L per matched unit.

        Returns:
            dict with:
                fill_pnl_by_ticker: dict mapping ticker -> {ticker, side,
                    realized_pnl, fees_paid, net_pnl, sell_count}
                total_gross_pnl: int (sum of realized_pnl across all tickers)
                total_fees: int (sum of fees across all tickers)

        Raises:
            PortfolioError: If fetching fills fails.
        """
        all_fills = self._fetch_all_fills()

        # Group fills by (ticker, side)
        groups = {}
        for fill in all_fills:
            key = (fill.get("ticker", "UNKNOWN"), fill.get("side", "yes"))
            if key not in groups:
                groups[key] = []
            groups[key].append(fill)

        fill_pnl_by_ticker = {}
        total_gross_pnl = 0
        total_fees = 0

        for (ticker, side), fills in groups.items():
            buy_fills = [f for f in fills if f.get("action") == "buy"]
            sell_fills = [f for f in fills if f.get("action") == "sell"]

            if not sell_fills:
                continue

            # Sort by created_time (oldest first) for FIFO matching
            buy_fills.sort(key=lambda f: f.get("created_time", ""))
            sell_fills.sort(key=lambda f: f.get("created_time", ""))

            price_field = "yes_price" if side == "yes" else "no_price"

            # FIFO matching
            realized_pnl = 0
            total_sell_count = 0
            buy_idx = 0
            buy_remaining = 0

            for sell in sell_fills:
                sell_count = sell.get("count", 0)
                sell_price = sell.get(price_field, 0)
                total_sell_count += sell_count

                remaining = sell_count
                while remaining > 0 and buy_idx < len(buy_fills):
                    if buy_remaining == 0:
                        buy_remaining = buy_fills[buy_idx].get("count", 0)

                    match_qty = min(remaining, buy_remaining)
                    buy_price = buy_fills[buy_idx].get(price_field, 0)

                    realized_pnl += match_qty * (sell_price - buy_price)

                    remaining -= match_qty
                    buy_remaining -= match_qty

                    if buy_remaining == 0:
                        buy_idx += 1

            # Sum fees from sell fills
            fees = 0
            for sell in sell_fills:
                fee_str = sell.get("fee_cost", "0")
                try:
                    fees += int(round(float(fee_str) * 100))
                except (ValueError, TypeError):
                    pass

            fill_pnl_by_ticker[ticker] = {
                "ticker": ticker,
                "side": side,
                "realized_pnl": realized_pnl,
                "fees_paid": fees,
                "net_pnl": realized_pnl - fees,
                "sell_count": total_sell_count,
            }

            total_gross_pnl += realized_pnl
            total_fees += fees

        return {
            "fill_pnl_by_ticker": fill_pnl_by_ticker,
            "total_gross_pnl": total_gross_pnl,
            "total_fees": total_fees,
        }

    # -------------------------------------------------------------------------
    # Public Methods
    # -------------------------------------------------------------------------

    def get_current_positions(self) -> list:
        """
        Get all open positions (where position quantity != 0).

        Returns:
            List of position dicts with non-zero positions.

        Raises:
            PortfolioError: If fetching positions fails.
        """
        all_positions = self._fetch_all_positions()
        return [p for p in all_positions if p.get("position", 0) != 0]

    def calculate_position_pnl(self, pos: dict) -> dict:
        """
        Calculate unrealized P&L for a single position.

        Args:
            pos: Position dict from the API with keys like ticker, position,
                 market_exposure, etc.

        Returns:
            dict with: ticker, title, quantity, side, avg_price, cost, value,
            pnl, status.

        Raises:
            PortfolioError: If market price lookup fails.
        """
        ticker = pos.get("ticker", "UNKNOWN")
        position = pos.get("position", 0)
        market_exposure = pos.get("market_exposure", 0)

        # Determine side and absolute quantity
        if position > 0:
            side = "yes"
            quantity = position
        else:
            side = "no"
            quantity = abs(position)

        # Cost basis from API's market_exposure
        cost = abs(market_exposure)

        # Average price per contract
        avg_price = (cost // quantity) if quantity else 0

        # Get current market data
        market = self._get_market_price(ticker)
        status = market.get("status", "unknown")
        title = market.get("title", "")
        result_value = market.get("result", "")

        # Calculate current value
        if result_value:
            # Settled market
            if result_value == "yes":
                value = quantity * 100 if side == "yes" else 0
            elif result_value == "no":
                value = 0 if side == "yes" else quantity * 100
            else:
                value = 0
        else:
            # Active market — use midpoint pricing
            yes_bid = market.get("yes_bid", 0)
            yes_ask = market.get("yes_ask", 0)

            if yes_bid and yes_ask:
                yes_mid = (yes_bid + yes_ask) // 2
            elif market.get("last_price"):
                yes_mid = market["last_price"]
            else:
                yes_mid = 0

            if side == "yes":
                value = quantity * yes_mid
            else:
                value = quantity * (100 - yes_mid)

        pnl = value - cost

        return {
            "ticker": ticker,
            "title": title,
            "quantity": quantity,
            "side": side,
            "avg_price": avg_price,
            "cost": cost,
            "value": value,
            "pnl": pnl,
            "status": status,
        }

    def calculate_total_pnl(self) -> dict:
        """
        Calculate aggregate unrealized P&L across all open positions.

        Positions that fail price lookup are skipped with a warning.

        Returns:
            dict with: total_cost, total_value, total_pnl, positions (list of
            per-position P&L dicts), errors (list of tickers that failed).

        Raises:
            PortfolioError: If fetching positions fails.
        """
        positions = self.get_current_positions()

        total_cost = 0
        total_value = 0
        total_pnl = 0
        pnl_details = []
        errors = []

        for pos in positions:
            ticker = pos.get("ticker", "UNKNOWN")
            try:
                pnl_info = self.calculate_position_pnl(pos)
                total_cost += pnl_info["cost"]
                total_value += pnl_info["value"]
                total_pnl += pnl_info["pnl"]
                pnl_details.append(pnl_info)
            except PortfolioError as e:
                logger.warning("Skipping position %s: %s", ticker, e)
                errors.append(ticker)

        return {
            "total_cost": total_cost,
            "total_value": total_value,
            "total_pnl": total_pnl,
            "positions": pnl_details,
            "errors": errors,
        }

    def get_realized_pnl(self) -> dict:
        """
        Get realized P&L from settled positions and fill-based sales.

        Uses the /portfolio/settlements endpoint for settled markets and
        fill data (FIFO matching) for positions sold before settlement.

        Returns:
            dict with: gross_pnl (total profit/loss before fees), total_fees,
            net_pnl (gross - fees), settlements (list of per-entry dicts
            with a "source" key indicating "settlement" or "fills").

        Raises:
            PortfolioError: If fetching settlements or fills fails.
        """
        all_settlements = self._fetch_all_settlements()

        gross_pnl = 0
        total_fees = 0
        settlement_details = []

        for s in all_settlements:
            revenue = s.get("revenue", 0)
            yes_cost = s.get("yes_total_cost", 0)
            no_cost = s.get("no_total_cost", 0)
            total_cost = yes_cost + no_cost

            # Parse fee_cost — API returns it as a dollar string like "0.0900"
            fee_str = s.get("fee_cost", "0")
            try:
                fees = int(round(float(fee_str) * 100))
            except (ValueError, TypeError):
                fees = 0

            pnl = revenue - total_cost

            settlement_details.append({
                "ticker": s.get("ticker", "UNKNOWN"),
                "market_result": s.get("market_result", ""),
                "revenue": revenue,
                "total_cost": total_cost,
                "realized_pnl": pnl,
                "fees_paid": fees,
                "net_pnl": pnl - fees,
                "source": "settlement",
            })
            gross_pnl += pnl
            total_fees += fees

        # Compute fill-based realized P&L for positions sold before settlement
        fill_results = self._compute_fill_based_realized_pnl()

        settled_tickers = {d["ticker"] for d in settlement_details}
        fill_tickers = set(fill_results["fill_pnl_by_ticker"].keys())

        # Warn about tickers with both sell fills and settlements
        ambiguous_tickers = settled_tickers & fill_tickers
        if ambiguous_tickers:
            sorted_ambiguous = sorted(ambiguous_tickers)
            logger.warning(
                "Ticker(s) %s have positions sold before market settlement. "
                "Realized P&L for these markets may be incomplete.",
                sorted_ambiguous,
            )
            print(
                f"  WARNING: Ticker(s) {sorted_ambiguous} have positions sold "
                f"before market settlement.\n"
                f"  Realized P&L for these markets may be incomplete — the "
                f"settlement data may not\n"
                f"  fully account for contracts sold early. Verify these "
                f"tickers manually."
            )

        # Add fill-based entries for tickers NOT in settlements
        for ticker, fill_data in fill_results["fill_pnl_by_ticker"].items():
            if ticker not in settled_tickers:
                settlement_details.append({
                    "ticker": fill_data["ticker"],
                    "side": fill_data["side"],
                    "realized_pnl": fill_data["realized_pnl"],
                    "fees_paid": fill_data["fees_paid"],
                    "net_pnl": fill_data["net_pnl"],
                    "sell_count": fill_data["sell_count"],
                    "source": "fills",
                })
                gross_pnl += fill_data["realized_pnl"]
                total_fees += fill_data["fees_paid"]

        return {
            "gross_pnl": gross_pnl,
            "total_fees": total_fees,
            "net_pnl": gross_pnl - total_fees,
            "settlements": settlement_details,
        }

    def display_portfolio_summary(self) -> None:
        """
        Print a formatted portfolio summary to stdout.

        Includes account balance, open positions with unrealized P&L,
        and realized P&L summary.
        """
        sep = "=" * 60
        dash = "-" * 56

        print(sep)
        print("  Portfolio Summary")
        print(sep)
        print()

        # Account balance
        try:
            balance_data = self.client.get_balance()
            balance = balance_data.get("balance", 0)
            portfolio_value = balance_data.get("portfolio_value", 0)
            total_value = balance + portfolio_value

            print(f"  Account Balance:    {_format_dollars(balance)}")
            print(f"  Portfolio Value:    {_format_dollars(portfolio_value)}")
            print(f"  Total Value:        {_format_dollars(total_value)}")
        except KalshiAPIError as e:
            logger.warning("Could not fetch balance: %s", e)
            print("  Account Balance:    (unavailable)")

        print()

        # Open positions
        print(f"  {dash}")
        print("  Open Positions")
        print(f"  {dash}")
        print()

        try:
            pnl_data = self.calculate_total_pnl()
            positions = pnl_data["positions"]

            if positions:
                for pos_pnl in positions:
                    _print_position_line(pos_pnl)
                    print()
            else:
                print("  No open positions.")
                print()

            if pnl_data["errors"]:
                print(f"  (Could not price: {', '.join(pnl_data['errors'])})")
                print()
        except PortfolioError as e:
            logger.warning("Could not fetch positions: %s", e)
            print("  (Could not load positions)")
            print()

        # Realized P&L
        print(f"  {dash}")
        print("  Realized P&L")
        print(f"  {dash}")
        print()

        try:
            realized = self.get_realized_pnl()
            print(f"  Gross P&L:          {_format_pnl(realized['gross_pnl'])}")
            print(f"  Fees Paid:          {_format_dollars(realized['total_fees'])}")
            print(f"  Net Realized P&L:   {_format_pnl(realized['net_pnl'])}")

            # Disclaimer when fill-sourced entries exist
            has_fill_entries = any(
                entry.get("source") == "fills"
                for entry in realized.get("settlements", [])
            )
            if has_fill_entries:
                print()
                print(
                    "  NOTE: Realized P&L from positions sold before market "
                    "settlement is"
                )
                print(
                    "  estimated from fill data. For markets where you sold "
                    "some contracts"
                )
                print(
                    "  and the remainder settled, the P&L may not fully "
                    "reflect early sales."
                )
        except PortfolioError as e:
            logger.warning("Could not fetch realized P&L: %s", e)
            print("  (Could not load realized P&L)")

        print()
        print(sep)
