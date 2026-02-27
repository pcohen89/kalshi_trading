# test_api_client.py - Test API integration (Task 7)
"""
Tests for the Kalshi API client.

Unit tests use mocking to test logic without API calls.
Integration tests use the sandbox environment for live testing.
"""

import base64
import os
import pytest
from unittest.mock import Mock, patch
from datetime import datetime, timezone

# Add parent directory to path for imports
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# =============================================================================
# Unit Tests (mocked, no actual API calls)
# =============================================================================

class TestKalshiClientUnit:
    """Unit tests with mocked dependencies."""

    @pytest.fixture
    def mock_config(self):
        """Mock the config module."""
        with patch('kalshi_client.get_api_credentials') as mock_creds, \
             patch('kalshi_client.get_api_base_url') as mock_url:

            # Generate a test RSA key
            from cryptography.hazmat.primitives.asymmetric import rsa
            from cryptography.hazmat.primitives import serialization

            private_key = rsa.generate_private_key(
                public_exponent=65537,
                key_size=2048,
            )
            pem = private_key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.PKCS8,
                encryption_algorithm=serialization.NoEncryption()
            ).decode('utf-8')

            mock_creds.return_value = ("test_api_key", pem)
            mock_url.return_value = "https://demo-api.kalshi.co/trade-api/v2"

            yield {
                'mock_creds': mock_creds,
                'mock_url': mock_url,
                'private_key_pem': pem,
            }

    def test_client_initialization(self, mock_config):
        """Test that client initializes correctly with config."""
        from kalshi_client import KalshiClient

        client = KalshiClient()

        assert client.api_key == "test_api_key"
        assert client.base_url == "https://demo-api.kalshi.co/trade-api/v2"
        assert client._private_key is not None

    def test_request_signing(self, mock_config):
        """Test that request signing produces valid base64 signature."""
        from kalshi_client import KalshiClient

        client = KalshiClient()

        # Timestamp must be Unix milliseconds (int)
        timestamp = 1705320000000  # 2024-01-15 12:00:00 UTC in milliseconds
        signature = client._sign_request("GET", "/trade-api/v2/portfolio/balance", timestamp)

        # Verify it's valid base64
        decoded = base64.b64decode(signature)
        assert len(decoded) > 0

    def test_auth_headers_generation(self, mock_config):
        """Test that auth headers are properly generated."""
        from kalshi_client import KalshiClient

        client = KalshiClient()

        headers = client._get_auth_headers("GET", "/trade-api/v2/portfolio/balance")

        assert "KALSHI-ACCESS-KEY" in headers
        assert "KALSHI-ACCESS-SIGNATURE" in headers
        assert "KALSHI-ACCESS-TIMESTAMP" in headers
        assert headers["KALSHI-ACCESS-KEY"] == "test_api_key"

    def test_place_order_validation_limit_no_price(self, mock_config):
        """Test that limit orders require a price."""
        from kalshi_client import KalshiClient, KalshiAPIError

        client = KalshiClient()

        with pytest.raises(KalshiAPIError) as exc_info:
            client.place_order(
                ticker="TEST-TICKER",
                side="yes",
                quantity=1,
                order_type="limit",
                price=None
            )

        assert "Price is required for limit orders" in str(exc_info.value)

    def test_place_order_validation_invalid_side(self, mock_config):
        """Test that side must be 'yes' or 'no'."""
        from kalshi_client import KalshiClient, KalshiAPIError

        client = KalshiClient()

        with pytest.raises(KalshiAPIError) as exc_info:
            client.place_order(
                ticker="TEST-TICKER",
                side="invalid",
                quantity=1,
                order_type="market"
            )

        assert "Side must be 'yes' or 'no'" in str(exc_info.value)

    def test_place_order_validation_invalid_action(self, mock_config):
        """Test that action must be 'buy' or 'sell'."""
        from kalshi_client import KalshiClient, KalshiAPIError

        client = KalshiClient()

        with pytest.raises(KalshiAPIError) as exc_info:
            client.place_order(
                ticker="TEST-TICKER",
                side="yes",
                quantity=1,
                action="invalid",
                order_type="market"
            )

        assert "Action must be 'buy' or 'sell'" in str(exc_info.value)

    def test_place_order_validation_negative_quantity(self, mock_config):
        """Test that quantity must be positive."""
        from kalshi_client import KalshiClient, KalshiAPIError

        client = KalshiClient()

        with pytest.raises(KalshiAPIError) as exc_info:
            client.place_order(
                ticker="TEST-TICKER",
                side="yes",
                quantity=-5,
                order_type="market"
            )

        assert "Quantity must be a positive integer" in str(exc_info.value)

    def test_place_order_validation_zero_quantity(self, mock_config):
        """Test that quantity cannot be zero."""
        from kalshi_client import KalshiClient, KalshiAPIError

        client = KalshiClient()

        with pytest.raises(KalshiAPIError) as exc_info:
            client.place_order(
                ticker="TEST-TICKER",
                side="yes",
                quantity=0,
                order_type="market"
            )

        assert "Quantity must be a positive integer" in str(exc_info.value)

    def test_place_order_validation_price_too_high(self, mock_config):
        """Test that price must be <= 99."""
        from kalshi_client import KalshiClient, KalshiAPIError

        client = KalshiClient()

        with pytest.raises(KalshiAPIError) as exc_info:
            client.place_order(
                ticker="TEST-TICKER",
                side="yes",
                quantity=1,
                order_type="limit",
                price=150
            )

        assert "Price must be an integer between 1 and 99" in str(exc_info.value)

    def test_place_order_validation_price_too_low(self, mock_config):
        """Test that price must be >= 1."""
        from kalshi_client import KalshiClient, KalshiAPIError

        client = KalshiClient()

        with pytest.raises(KalshiAPIError) as exc_info:
            client.place_order(
                ticker="TEST-TICKER",
                side="yes",
                quantity=1,
                order_type="limit",
                price=0
            )

        assert "Price must be an integer between 1 and 99" in str(exc_info.value)

    @patch('requests.Session.request')
    def test_retry_on_server_error(self, mock_request, mock_config):
        """Test that client retries on 500 errors."""
        from kalshi_client import KalshiClient

        # First two calls return 500, third succeeds
        mock_response_500 = Mock()
        mock_response_500.status_code = 500

        mock_response_200 = Mock()
        mock_response_200.status_code = 200
        mock_response_200.json.return_value = {"balance": 10000}

        mock_request.side_effect = [mock_response_500, mock_response_500, mock_response_200]

        client = KalshiClient()
        # Reduce backoff for faster tests
        client.RETRY_BACKOFF_BASE = 0.01

        result = client.get_balance()

        assert result == {"balance": 10000}
        assert mock_request.call_count == 3

    @patch('requests.Session.request')
    def test_no_retry_on_401(self, mock_request, mock_config):
        """Test that client does not retry on authentication errors."""
        from kalshi_client import KalshiClient, KalshiAPIError

        mock_response = Mock()
        mock_response.status_code = 401
        mock_request.return_value = mock_response

        client = KalshiClient()

        with pytest.raises(KalshiAPIError) as exc_info:
            client.get_balance()

        assert exc_info.value.status_code == 401
        assert "Authentication failed" in str(exc_info.value)
        # Should only try once
        assert mock_request.call_count == 1

    @patch('requests.Session.request')
    def test_rate_limit_handling(self, mock_request, mock_config):
        """Test that client waits on rate limit."""
        from kalshi_client import KalshiClient

        mock_response_429 = Mock()
        mock_response_429.status_code = 429
        mock_response_429.headers = {"Retry-After": "1"}

        mock_response_200 = Mock()
        mock_response_200.status_code = 200
        mock_response_200.json.return_value = {"balance": 10000}

        mock_request.side_effect = [mock_response_429, mock_response_200]

        client = KalshiClient()

        result = client.get_balance()

        assert result == {"balance": 10000}
        assert mock_request.call_count == 2

    @patch('requests.Session.request')
    def test_error_parsing(self, mock_request, mock_config):
        """Test that API errors are parsed into exceptions."""
        from kalshi_client import KalshiClient, KalshiAPIError

        mock_response = Mock()
        mock_response.status_code = 400
        mock_response.json.return_value = {"message": "Invalid ticker"}
        mock_request.return_value = mock_response

        client = KalshiClient()

        with pytest.raises(KalshiAPIError) as exc_info:
            client.get_market("INVALID")

        assert exc_info.value.status_code == 400
        assert "Invalid ticker" in str(exc_info.value)

    @patch('requests.Session.request')
    def test_204_no_content(self, mock_request, mock_config):
        """Test handling of 204 No Content responses."""
        from kalshi_client import KalshiClient

        mock_response = Mock()
        mock_response.status_code = 204
        mock_request.return_value = mock_response

        client = KalshiClient()

        result = client.cancel_order("test-order-id")

        assert result == {}


class TestKalshiAPIError:
    """Tests for the KalshiAPIError exception class."""

    def test_error_with_status_code(self):
        """Test error string formatting with status code."""
        from kalshi_client import KalshiAPIError

        error = KalshiAPIError("Test error", status_code=400)
        assert str(error) == "KalshiAPIError (400): Test error"

    def test_error_without_status_code(self):
        """Test error string formatting without status code."""
        from kalshi_client import KalshiAPIError

        error = KalshiAPIError("Test error")
        assert str(error) == "KalshiAPIError: Test error"

    def test_error_with_response_body(self):
        """Test that response body is stored."""
        from kalshi_client import KalshiAPIError

        body = {"code": "INVALID_TICKER", "details": "xyz"}
        error = KalshiAPIError("Test error", status_code=400, response_body=body)

        assert error.response_body == body


# =============================================================================
# Historical + Candlestick Method Tests (Task 9)
# =============================================================================

class TestKalshiClientHistoricalMethods:
    """Tests for get_historical_cutoff, get_historical_markets,
    get_market_candlesticks, and get_batch_candlesticks."""

    @pytest.fixture
    def mock_config(self):
        """Mock config module — identical to TestKalshiClientUnit fixture."""
        with patch('kalshi_client.get_api_credentials') as mock_creds, \
             patch('kalshi_client.get_api_base_url') as mock_url:
            from cryptography.hazmat.primitives.asymmetric import rsa
            from cryptography.hazmat.primitives import serialization

            private_key = rsa.generate_private_key(
                public_exponent=65537,
                key_size=2048,
            )
            pem = private_key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.PKCS8,
                encryption_algorithm=serialization.NoEncryption()
            ).decode('utf-8')

            mock_creds.return_value = ("test_api_key", pem)
            mock_url.return_value = "https://demo-api.kalshi.co/trade-api/v2"
            yield

    @pytest.fixture
    def client(self, mock_config):
        from kalshi_client import KalshiClient
        return KalshiClient()

    def test_get_historical_cutoff_calls_correct_endpoint(self, client):
        client._make_request = Mock(return_value={"live_cutoff_ts": 1000, "historical_cutoff_ts": 900})
        result = client.get_historical_cutoff()
        client._make_request.assert_called_once_with("GET", "/historical/cutoff")
        assert result["live_cutoff_ts"] == 1000

    def test_get_historical_markets_no_filters(self, client):
        client._make_request = Mock(return_value={"markets": [], "cursor": ""})
        client.get_historical_markets()
        call_args = client._make_request.call_args
        assert call_args[0][1] == "/historical/markets"
        assert call_args[1]["params"]["limit"] == 1000
        assert "series_ticker" not in call_args[1]["params"]

    def test_get_historical_markets_with_series_ticker(self, client):
        client._make_request = Mock(return_value={"markets": [], "cursor": ""})
        client.get_historical_markets(series_ticker="KXBTC")
        call_args = client._make_request.call_args
        assert call_args[1]["params"]["series_ticker"] == "KXBTC"

    def test_get_historical_markets_with_cursor(self, client):
        client._make_request = Mock(return_value={"markets": [], "cursor": ""})
        client.get_historical_markets(cursor="abc123")
        call_args = client._make_request.call_args
        assert call_args[1]["params"]["cursor"] == "abc123"

    def test_get_historical_markets_with_tickers_list(self, client):
        client._make_request = Mock(return_value={"markets": [], "cursor": ""})
        client.get_historical_markets(tickers=["KXBTC-A", "KXBTC-B"])
        call_args = client._make_request.call_args
        assert call_args[1]["params"]["tickers"] == "KXBTC-A,KXBTC-B"

    def test_get_market_candlesticks_live_path(self, client):
        client._make_request = Mock(return_value={"candlesticks": []})
        client.get_market_candlesticks("KXBTC-25DEC", historical=False)
        call_args = client._make_request.call_args
        assert call_args[0][1] == "/markets/KXBTC-25DEC/candlesticks"

    def test_get_market_candlesticks_historical_path(self, client):
        client._make_request = Mock(return_value={"candlesticks": []})
        client.get_market_candlesticks("KXBTC-25DEC", historical=True)
        call_args = client._make_request.call_args
        assert call_args[0][1] == "/historical/markets/KXBTC-25DEC/candlesticks"

    def test_get_market_candlesticks_default_period_interval(self, client):
        client._make_request = Mock(return_value={"candlesticks": []})
        client.get_market_candlesticks("KXBTC-25DEC")
        call_args = client._make_request.call_args
        assert call_args[1]["params"]["period_interval"] == 1440

    def test_get_market_candlesticks_with_start_end_ts(self, client):
        client._make_request = Mock(return_value={"candlesticks": []})
        client.get_market_candlesticks("KXBTC-25DEC", start_ts=1000, end_ts=2000)
        call_args = client._make_request.call_args
        assert call_args[1]["params"]["start_ts"] == 1000
        assert call_args[1]["params"]["end_ts"] == 2000

    def test_get_market_candlesticks_omits_none_ts(self, client):
        client._make_request = Mock(return_value={"candlesticks": []})
        client.get_market_candlesticks("KXBTC-25DEC")
        call_args = client._make_request.call_args
        assert "start_ts" not in call_args[1]["params"]
        assert "end_ts" not in call_args[1]["params"]

    def test_get_batch_candlesticks_comma_separates_tickers(self, client):
        client._make_request = Mock(return_value={"candlesticks": {}})
        client.get_batch_candlesticks(["KXBTC-A", "KXBTC-B", "KXBTC-C"])
        call_args = client._make_request.call_args
        assert call_args[0][1] == "/markets/candlesticks"
        assert call_args[1]["params"]["tickers"] == "KXBTC-A,KXBTC-B,KXBTC-C"

    def test_get_batch_candlesticks_returns_dict_by_ticker(self, client):
        expected = {"candlesticks": {"KXBTC-A": [{"volume": 100}]}}
        client._make_request = Mock(return_value=expected)
        result = client.get_batch_candlesticks(["KXBTC-A"])
        assert result == expected

    def test_get_batch_candlesticks_100_tickers(self, client):
        tickers = [f"KXBTC-{i:03d}" for i in range(100)]
        client._make_request = Mock(return_value={"candlesticks": {}})
        client.get_batch_candlesticks(tickers)
        call_args = client._make_request.call_args
        assert len(call_args[1]["params"]["tickers"].split(",")) == 100

    def test_get_historical_cutoff_raises_on_api_error(self, client):
        from kalshi_client import KalshiAPIError
        client._make_request = Mock(side_effect=KalshiAPIError("server error", status_code=500))
        with pytest.raises(KalshiAPIError):
            client.get_historical_cutoff()

    def test_get_historical_markets_raises_on_api_error(self, client):
        from kalshi_client import KalshiAPIError
        client._make_request = Mock(side_effect=KalshiAPIError("server error", status_code=500))
        with pytest.raises(KalshiAPIError):
            client.get_historical_markets()

    def test_get_batch_candlesticks_raises_on_empty_tickers(self, client):
        from kalshi_client import KalshiAPIError
        with pytest.raises(KalshiAPIError, match="empty"):
            client.get_batch_candlesticks([])


# =============================================================================
# Integration Tests (requires sandbox credentials)
# =============================================================================

@pytest.mark.integration
class TestKalshiClientIntegration:
    """
    Integration tests that run against the Kalshi sandbox API.

    Run with: pytest -m integration tests/test_api_client.py

    Requires valid sandbox credentials in .env file.
    """

    @pytest.fixture
    def client(self):
        """Create a real client for integration tests."""
        from kalshi_client import KalshiClient
        return KalshiClient()

    def test_authentication(self, client):
        """Test that we can authenticate successfully."""
        # If we can get balance, authentication worked
        result = client.get_balance()
        assert "balance" in result

    def test_get_balance(self, client):
        """Test getting account balance."""
        result = client.get_balance()

        # Should have balance fields
        assert isinstance(result, dict)
        # Balance should be a number (in cents)

    def test_get_positions(self, client):
        """Test getting positions list."""
        result = client.get_positions()

        # Should return a dict with positions key
        assert isinstance(result, dict)
        # May be empty but should have the structure

    def test_get_markets(self, client):
        """Test getting markets list."""
        result = client.get_markets(limit=5)

        assert isinstance(result, dict)
        assert "markets" in result
        assert isinstance(result["markets"], list)

        if len(result["markets"]) > 0:
            market = result["markets"][0]
            # Markets should have ticker
            assert "ticker" in market

    def test_get_orders(self, client):
        """Test getting orders list."""
        result = client.get_orders(limit=5)

        assert isinstance(result, dict)
        assert "orders" in result

    def test_get_fills(self, client):
        """Test getting fills list."""
        result = client.get_fills(limit=5)

        assert isinstance(result, dict)
        assert "fills" in result

    def test_order_lifecycle(self, client):
        """
        Test placing and cancelling an order.

        Places a limit order far from market price so it won't fill,
        then cancels it.
        """
        # First get an open market
        markets = client.get_markets(limit=10, status="open")

        if not markets.get("markets"):
            pytest.skip("No open markets available for testing")

        # Pick the first open market
        market = markets["markets"][0]
        ticker = market["ticker"]

        order_id = None
        try:
            order_result = client.place_order(
                ticker=ticker,
                side="yes",
                quantity=1,
                order_type="limit",
                price=1  # 1 cent - very unlikely to fill
            )

            assert "order" in order_result
            order_id = order_result["order"]["order_id"]

            # Get order status
            order_status = client.get_order(order_id)
            assert order_status is not None

            # Cancel the order
            client.cancel_order(order_id)
            order_id = None  # Successfully cancelled, no cleanup needed
        finally:
            # Always attempt to cancel if order was placed but not yet cancelled
            if order_id is not None:
                try:
                    client.cancel_order(order_id)
                except Exception:
                    pass  # Best-effort cleanup


# =============================================================================
# Pytest configuration
# =============================================================================

def pytest_configure(config):
    """Register custom markers."""
    config.addinivalue_line(
        "markers", "integration: marks tests as integration tests (requires API credentials)"
    )
