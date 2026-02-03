# test_trade_executor.py - Unit tests for trade executor (Task 2)
"""
Unit tests for the TradeExecutor class.

These tests use mocked KalshiClient to test validation logic
and error handling without making real API calls.
"""

import pytest
from unittest.mock import Mock, patch

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from trade_executor import TradeExecutor, TradeExecutionError
from kalshi_client import KalshiAPIError


@pytest.fixture
def mock_client():
    """Create a mock KalshiClient."""
    return Mock()


@pytest.fixture
def executor(mock_client):
    """Create a TradeExecutor with a mock client."""
    return TradeExecutor(client=mock_client)


# =============================================================================
# Market Order Tests
# =============================================================================

class TestPlaceMarketOrder:
    """Tests for place_market_order method."""

    def test_place_market_order_success(self, executor, mock_client):
        """Valid market order returns order details."""
        mock_client.place_order.return_value = {
            "order": {
                "order_id": "abc123",
                "ticker": "TEST-TICKER",
                "side": "yes",
                "status": "resting"
            }
        }

        result = executor.place_market_order("TEST-TICKER", "yes", 10)

        mock_client.place_order.assert_called_once_with(
            ticker="TEST-TICKER",
            side="yes",
            quantity=10,
            action="buy",
            order_type="market"
        )
        assert result["order"]["order_id"] == "abc123"

    def test_place_market_order_no_side(self, executor, mock_client):
        """Valid market order with 'no' side."""
        mock_client.place_order.return_value = {"order": {"order_id": "xyz789"}}

        result = executor.place_market_order("TEST-TICKER", "no", 5)

        mock_client.place_order.assert_called_once_with(
            ticker="TEST-TICKER",
            side="no",
            quantity=5,
            action="buy",
            order_type="market"
        )

    def test_place_market_order_invalid_side(self, executor, mock_client):
        """Rejects side other than 'yes' or 'no'."""
        with pytest.raises(TradeExecutionError) as exc_info:
            executor.place_market_order("TEST-TICKER", "maybe", 10)

        assert "Side must be 'yes' or 'no'" in str(exc_info.value)
        mock_client.place_order.assert_not_called()

    def test_place_market_order_invalid_side_empty(self, executor, mock_client):
        """Rejects empty side."""
        with pytest.raises(TradeExecutionError) as exc_info:
            executor.place_market_order("TEST-TICKER", "", 10)

        assert "Side must be 'yes' or 'no'" in str(exc_info.value)

    def test_place_market_order_invalid_quantity_zero(self, executor, mock_client):
        """Rejects zero quantity."""
        with pytest.raises(TradeExecutionError) as exc_info:
            executor.place_market_order("TEST-TICKER", "yes", 0)

        assert "Quantity must be a positive integer" in str(exc_info.value)
        mock_client.place_order.assert_not_called()

    def test_place_market_order_invalid_quantity_negative(self, executor, mock_client):
        """Rejects negative quantity."""
        with pytest.raises(TradeExecutionError) as exc_info:
            executor.place_market_order("TEST-TICKER", "yes", -5)

        assert "Quantity must be a positive integer" in str(exc_info.value)

    def test_place_market_order_invalid_quantity_float(self, executor, mock_client):
        """Rejects float quantity."""
        with pytest.raises(TradeExecutionError) as exc_info:
            executor.place_market_order("TEST-TICKER", "yes", 10.5)

        assert "Quantity must be a positive integer" in str(exc_info.value)

    def test_place_market_order_api_error(self, executor, mock_client):
        """Handles API errors gracefully."""
        mock_client.place_order.side_effect = KalshiAPIError("Insufficient balance", status_code=400)

        with pytest.raises(TradeExecutionError) as exc_info:
            executor.place_market_order("TEST-TICKER", "yes", 10)

        assert "Failed to place market order" in str(exc_info.value)


# =============================================================================
# Limit Order Tests
# =============================================================================

class TestPlaceLimitOrder:
    """Tests for place_limit_order method."""

    def test_place_limit_order_success(self, executor, mock_client):
        """Valid limit order returns order details."""
        mock_client.place_order.return_value = {
            "order": {
                "order_id": "limit123",
                "ticker": "TEST-TICKER",
                "side": "yes",
                "yes_price": 55,
                "status": "resting"
            }
        }

        result = executor.place_limit_order("TEST-TICKER", "yes", 10, 55)

        mock_client.place_order.assert_called_once_with(
            ticker="TEST-TICKER",
            side="yes",
            quantity=10,
            action="buy",
            order_type="limit",
            price=55
        )
        assert result["order"]["order_id"] == "limit123"

    def test_place_limit_order_invalid_price_low(self, executor, mock_client):
        """Rejects price less than 1."""
        with pytest.raises(TradeExecutionError) as exc_info:
            executor.place_limit_order("TEST-TICKER", "yes", 10, 0)

        assert "Price must be an integer between 1 and 99 cents" in str(exc_info.value)
        mock_client.place_order.assert_not_called()

    def test_place_limit_order_invalid_price_high(self, executor, mock_client):
        """Rejects price greater than 99."""
        with pytest.raises(TradeExecutionError) as exc_info:
            executor.place_limit_order("TEST-TICKER", "yes", 10, 100)

        assert "Price must be an integer between 1 and 99 cents" in str(exc_info.value)

    def test_place_limit_order_invalid_price_none(self, executor, mock_client):
        """Rejects None price."""
        with pytest.raises(TradeExecutionError) as exc_info:
            executor.place_limit_order("TEST-TICKER", "yes", 10, None)

        assert "Price is required for limit orders" in str(exc_info.value)

    def test_place_limit_order_invalid_price_float(self, executor, mock_client):
        """Rejects float price."""
        with pytest.raises(TradeExecutionError) as exc_info:
            executor.place_limit_order("TEST-TICKER", "yes", 10, 55.5)

        assert "Price must be an integer between 1 and 99 cents" in str(exc_info.value)

    def test_place_limit_order_edge_price_1(self, executor, mock_client):
        """Accepts minimum valid price of 1."""
        mock_client.place_order.return_value = {"order": {"order_id": "edge1"}}

        result = executor.place_limit_order("TEST-TICKER", "yes", 1, 1)

        mock_client.place_order.assert_called_once()
        assert "order" in result

    def test_place_limit_order_edge_price_99(self, executor, mock_client):
        """Accepts maximum valid price of 99."""
        mock_client.place_order.return_value = {"order": {"order_id": "edge99"}}

        result = executor.place_limit_order("TEST-TICKER", "no", 1, 99)

        mock_client.place_order.assert_called_once()

    def test_place_limit_order_api_error(self, executor, mock_client):
        """Handles API errors gracefully."""
        mock_client.place_order.side_effect = KalshiAPIError("Market closed", status_code=400)

        with pytest.raises(TradeExecutionError) as exc_info:
            executor.place_limit_order("TEST-TICKER", "yes", 10, 50)

        assert "Failed to place limit order" in str(exc_info.value)


# =============================================================================
# Cancel Order Tests
# =============================================================================

class TestCancelOrder:
    """Tests for cancel_order method."""

    def test_cancel_order_success(self, executor, mock_client):
        """Cancels order and returns confirmation."""
        mock_client.cancel_order.return_value = {
            "order": {
                "order_id": "abc123",
                "status": "canceled"
            }
        }

        result = executor.cancel_order("abc123")

        mock_client.cancel_order.assert_called_once_with("abc123")
        assert result["order"]["status"] == "canceled"

    def test_cancel_order_empty_id(self, executor, mock_client):
        """Rejects empty order ID."""
        with pytest.raises(TradeExecutionError) as exc_info:
            executor.cancel_order("")

        assert "Order ID cannot be empty" in str(exc_info.value)
        mock_client.cancel_order.assert_not_called()

    def test_cancel_order_whitespace_id(self, executor, mock_client):
        """Rejects whitespace-only order ID."""
        with pytest.raises(TradeExecutionError) as exc_info:
            executor.cancel_order("   ")

        assert "Order ID cannot be empty" in str(exc_info.value)

    def test_cancel_order_not_found(self, executor, mock_client):
        """Handles non-existent order ID."""
        mock_client.cancel_order.side_effect = KalshiAPIError("Order not found", status_code=404)

        with pytest.raises(TradeExecutionError) as exc_info:
            executor.cancel_order("nonexistent")

        assert "Failed to cancel order" in str(exc_info.value)


# =============================================================================
# Order Status Tests
# =============================================================================

class TestGetOrderStatus:
    """Tests for get_order_status method."""

    def test_get_order_status_success(self, executor, mock_client):
        """Returns order with status."""
        mock_client.get_order.return_value = {
            "order": {
                "order_id": "abc123",
                "status": "executed",
                "ticker": "TEST-TICKER"
            }
        }

        result = executor.get_order_status("abc123")

        mock_client.get_order.assert_called_once_with("abc123")
        assert result["order"]["status"] == "executed"

    def test_get_order_status_empty_id(self, executor, mock_client):
        """Rejects empty order ID."""
        with pytest.raises(TradeExecutionError) as exc_info:
            executor.get_order_status("")

        assert "Order ID cannot be empty" in str(exc_info.value)

    def test_get_order_status_not_found(self, executor, mock_client):
        """Handles non-existent order ID."""
        mock_client.get_order.side_effect = KalshiAPIError("Order not found", status_code=404)

        with pytest.raises(TradeExecutionError) as exc_info:
            executor.get_order_status("nonexistent")

        assert "Failed to get order status" in str(exc_info.value)


# =============================================================================
# List Open Orders Tests
# =============================================================================

class TestListOpenOrders:
    """Tests for list_open_orders method."""

    def test_list_open_orders_success(self, executor, mock_client):
        """Returns list of resting orders."""
        mock_client.get_orders.return_value = {
            "orders": [
                {"order_id": "order1", "status": "resting"},
                {"order_id": "order2", "status": "resting"}
            ]
        }

        result = executor.list_open_orders()

        mock_client.get_orders.assert_called_once_with(status="resting")
        assert len(result) == 2
        assert result[0]["order_id"] == "order1"

    def test_list_open_orders_empty(self, executor, mock_client):
        """Handles no open orders."""
        mock_client.get_orders.return_value = {"orders": []}

        result = executor.list_open_orders()

        assert result == []

    def test_list_open_orders_api_error(self, executor, mock_client):
        """Handles API errors gracefully."""
        mock_client.get_orders.side_effect = KalshiAPIError("Server error", status_code=500)

        with pytest.raises(TradeExecutionError) as exc_info:
            executor.list_open_orders()

        assert "Failed to list open orders" in str(exc_info.value)


# =============================================================================
# Market Info & Validation Tests
# =============================================================================

class TestGetMarketInfo:
    """Tests for get_market_info method."""

    def test_get_market_info_success(self, executor, mock_client):
        """Returns market details."""
        mock_client.get_market.return_value = {
            "market": {
                "ticker": "TEST-TICKER",
                "title": "Test Market",
                "status": "open"
            }
        }

        result = executor.get_market_info("TEST-TICKER")

        mock_client.get_market.assert_called_once_with("TEST-TICKER")
        assert result["ticker"] == "TEST-TICKER"
        assert result["status"] == "open"

    def test_get_market_info_empty_ticker(self, executor, mock_client):
        """Rejects empty ticker."""
        with pytest.raises(TradeExecutionError) as exc_info:
            executor.get_market_info("")

        assert "Ticker cannot be empty" in str(exc_info.value)

    def test_get_market_info_not_found(self, executor, mock_client):
        """Handles non-existent ticker."""
        mock_client.get_market.side_effect = KalshiAPIError("Market not found", status_code=404)

        with pytest.raises(TradeExecutionError) as exc_info:
            executor.get_market_info("FAKE-TICKER")

        assert "Failed to get market info" in str(exc_info.value)


class TestValidateTicker:
    """Tests for validate_ticker method."""

    def test_validate_ticker_exists_and_open(self, executor, mock_client):
        """Returns True for valid open market."""
        mock_client.get_market.return_value = {
            "market": {"ticker": "TEST-TICKER", "status": "open"}
        }

        result = executor.validate_ticker("TEST-TICKER")

        assert result is True

    def test_validate_ticker_exists_but_closed(self, executor, mock_client):
        """Returns False for closed market."""
        mock_client.get_market.return_value = {
            "market": {"ticker": "TEST-TICKER", "status": "closed"}
        }

        result = executor.validate_ticker("TEST-TICKER")

        assert result is False

    def test_validate_ticker_not_found(self, executor, mock_client):
        """Returns False for non-existent ticker."""
        mock_client.get_market.side_effect = KalshiAPIError("Not found", status_code=404)

        result = executor.validate_ticker("FAKE-TICKER")

        assert result is False


# =============================================================================
# Search Markets Tests
# =============================================================================

class TestSearchMarkets:
    """Tests for search_markets method."""

    def test_search_markets_no_query_returns_markets(self, executor, mock_client):
        """Without query, returns list of markets."""
        mock_client.get_markets.return_value = {
            "markets": [
                {"ticker": "BTC-100K", "title": "Bitcoin $100k", "status": "open"},
                {"ticker": "ETH-50K", "title": "Ethereum $50k", "status": "open"}
            ]
        }

        result = executor.search_markets()

        assert mock_client.get_markets.called
        assert len(result) == 2
        assert result[0]["ticker"] == "BTC-100K"

    def test_search_markets_with_query_filters(self, executor, mock_client):
        """With query, filters markets by title."""
        mock_client.get_markets.return_value = {
            "markets": [
                {"ticker": "BTC-100K", "title": "Bitcoin $100k", "status": "open"},
                {"ticker": "ETH-50K", "title": "Ethereum $50k", "status": "open"},
                {"ticker": "SP500-5000", "title": "S&P 500 at 5000", "status": "open"}
            ]
        }

        result = executor.search_markets(query="bitcoin")

        assert len(result) == 1
        assert result[0]["ticker"] == "BTC-100K"

    def test_search_markets_query_matches_ticker(self, executor, mock_client):
        """Query can match ticker as well as title."""
        mock_client.get_markets.return_value = {
            "markets": [
                {"ticker": "BTC-100K", "title": "Will price hit target?", "status": "open"},
                {"ticker": "ETH-50K", "title": "Ethereum price", "status": "open"}
            ]
        }

        result = executor.search_markets(query="btc")

        assert len(result) == 1
        assert result[0]["ticker"] == "BTC-100K"

    def test_search_markets_query_case_insensitive(self, executor, mock_client):
        """Query matching is case-insensitive."""
        mock_client.get_markets.return_value = {
            "markets": [
                {"ticker": "BTC-100K", "title": "BITCOIN Price", "status": "open"}
            ]
        }

        result = executor.search_markets(query="BiTcOiN")

        assert len(result) == 1

    def test_search_markets_no_results(self, executor, mock_client):
        """Returns empty list when no matches."""
        mock_client.get_markets.return_value = {
            "markets": [
                {"ticker": "BTC-100K", "title": "Bitcoin $100k", "status": "open"}
            ]
        }

        result = executor.search_markets(query="dogecoin")

        assert result == []

    def test_search_markets_respects_limit(self, executor, mock_client):
        """Respects limit parameter."""
        mock_client.get_markets.return_value = {
            "markets": [
                {"ticker": f"MKT-{i}", "title": f"Market {i}", "status": "open"}
                for i in range(10)
            ]
        }

        result = executor.search_markets(query="market", limit=3)

        assert len(result) == 3

    def test_search_markets_with_series_ticker(self, executor, mock_client):
        """Respects series_ticker parameter."""
        mock_client.get_markets.return_value = {
            "markets": [
                {"ticker": "PRES-2024", "title": "Election market", "status": "open"}
            ]
        }

        result = executor.search_markets(query="election", series_ticker="PRES")

        # Should only search the specified series
        mock_client.get_markets.assert_called_once()
        call_kwargs = mock_client.get_markets.call_args[1]
        assert call_kwargs["series_ticker"] == "PRES"

    def test_search_markets_api_error(self, executor, mock_client):
        """Handles API errors gracefully when no query."""
        mock_client.get_markets.side_effect = KalshiAPIError("Server error", status_code=500)

        with pytest.raises(TradeExecutionError) as exc_info:
            executor.search_markets()

        assert "Failed to search markets" in str(exc_info.value)
