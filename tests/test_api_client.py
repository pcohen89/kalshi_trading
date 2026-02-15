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
