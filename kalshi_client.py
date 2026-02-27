# kalshi_client.py - API integration (Task 1)
"""
Kalshi API client for the Trading System.

Provides authenticated access to Kalshi's trading API with:
- RSA-based request signing
- Automatic retry with exponential backoff
- Comprehensive error handling
- Request/response logging
"""

import base64
import logging
import os
import time
from datetime import datetime, timezone
from typing import Optional, Union

import requests
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives.asymmetric.types import PrivateKeyTypes
from cryptography.hazmat.backends import default_backend

from config import get_api_credentials, get_api_base_url


# Configure module logger
logger = logging.getLogger(__name__)


class KalshiAPIError(Exception):
    """Exception raised for Kalshi API errors."""

    def __init__(self, message: str, status_code: Optional[int] = None, response_body: Optional[dict] = None):
        self.message = message
        self.status_code = status_code
        self.response_body = response_body
        super().__init__(self.message)

    def __str__(self):
        if self.status_code:
            return f"KalshiAPIError ({self.status_code}): {self.message}"
        return f"KalshiAPIError: {self.message}"


class KalshiClient:
    """
    Client for interacting with the Kalshi Trading API.

    Usage:
        # Load credentials from config/.env automatically
        client = KalshiClient()

        # Or inject credentials directly
        client = KalshiClient(api_key="key", api_secret="./key.pem", base_url="https://...")

        balance = client.get_balance()
    """

    # Retry configuration
    MAX_RETRIES = 3
    MAX_RATE_LIMIT_RETRIES = 5  # Separate limit for rate limiting
    RETRY_BACKOFF_BASE = 1.0  # seconds
    RETRY_STATUS_CODES = {500, 502, 503, 504}  # Server errors worth retrying

    def __init__(
        self,
        api_key: Optional[str] = None,
        api_secret: Optional[str] = None,
        base_url: Optional[str] = None,
    ):
        """
        Initialize the Kalshi client.

        Args:
            api_key: API key. Loaded from config if not provided.
            api_secret: API secret (PEM key path or string). Loaded from config if not provided.
            base_url: API base URL. Loaded from config if not provided.
        """
        if api_key and api_secret:
            self.api_key = api_key
            self.api_secret = api_secret
        else:
            self.api_key, self.api_secret = get_api_credentials()

        self.base_url = base_url or get_api_base_url()

        # Load private key for signing
        self._private_key = self._load_private_key(self.api_secret)

        # Setup session for connection reuse
        self.session = requests.Session()
        self.session.headers.update({
            "Content-Type": "application/json",
            "Accept": "application/json",
        })

        logger.info("KalshiClient initialized for %s", self.base_url)

    def _load_private_key(self, key_data: str) -> PrivateKeyTypes:
        """
        Load RSA private key from PEM string or file path.

        Supports multiple formats:
        - Direct PEM string (multiline)
        - Single line with literal \\n characters
        - File path to a .pem file
        """
        try:
            # Check if key_data is a file path
            if key_data.endswith('.pem') or key_data.startswith('/') or key_data.startswith('./'):
                key_path = key_data
                if not os.path.isabs(key_path):
                    # Relative to project directory
                    key_path = os.path.join(os.path.dirname(__file__), key_path)

                if not os.path.exists(key_path):
                    raise KalshiAPIError(f"Private key file not found: {key_path}")

                with open(key_path, 'rb') as f:
                    key_bytes = f.read()
            else:
                # Handle key stored as single line with \n literals
                if "\\n" in key_data:
                    key_data = key_data.replace("\\n", "\n")

                key_bytes = key_data.encode("utf-8")

            private_key = serialization.load_pem_private_key(
                key_bytes,
                password=None,
                backend=default_backend()
            )
            return private_key
        except KalshiAPIError:
            raise
        except Exception as e:
            raise KalshiAPIError(
                f"Failed to load private key: {e}\n"
                "Ensure KALSHI_API_SECRET is either:\n"
                "  1. A path to your .pem file (e.g., ./kalshi_private_key.pem)\n"
                "  2. The key as a single line with \\n for newlines"
            )

    def _sign_request(self, method: str, path: str, timestamp: int) -> str:
        """
        Create RSA-PSS signature for request authentication.

        Args:
            method: HTTP method (GET, POST, DELETE)
            path: API path (e.g., /trade-api/v2/portfolio/balance)
            timestamp: Unix timestamp in milliseconds

        Returns:
            Base64-encoded signature
        """
        # Message format: timestamp + method + path
        message = f"{timestamp}{method}{path}"
        message_bytes = message.encode("utf-8")

        # Sign with RSA-PSS (salt_length must be DIGEST_LENGTH per Kalshi docs)
        signature = self._private_key.sign(
            message_bytes,
            padding.PSS(
                mgf=padding.MGF1(hashes.SHA256()),
                salt_length=padding.PSS.DIGEST_LENGTH
            ),
            hashes.SHA256()
        )

        return base64.b64encode(signature).decode("utf-8")

    def _get_auth_headers(self, method: str, path: str) -> dict:
        """Generate authentication headers for a request."""
        # Timestamp must be Unix milliseconds per Kalshi API docs
        timestamp = int(datetime.now(timezone.utc).timestamp() * 1000)
        signature = self._sign_request(method, path, timestamp)

        return {
            "KALSHI-ACCESS-KEY": self.api_key,
            "KALSHI-ACCESS-SIGNATURE": signature,
            "KALSHI-ACCESS-TIMESTAMP": str(timestamp),
        }

    def _make_request(
        self,
        method: str,
        endpoint: str,
        params: Optional[dict] = None,
        json_data: Optional[dict] = None,
    ) -> dict:
        """
        Make an authenticated request to the Kalshi API.

        Args:
            method: HTTP method
            endpoint: API endpoint (without base URL)
            params: Query parameters
            json_data: JSON body for POST requests

        Returns:
            Parsed JSON response

        Raises:
            KalshiAPIError: On API errors or after max retries
        """
        url = f"{self.base_url}{endpoint}"
        path = f"/trade-api/v2{endpoint}"

        last_exception = None
        rate_limit_retries = 0

        for attempt in range(self.MAX_RETRIES):
            try:
                # Generate fresh auth headers for each attempt
                auth_headers = self._get_auth_headers(method, path)
                headers = {**self.session.headers, **auth_headers}

                logger.info("API Request: %s %s (attempt %d)", method, endpoint, attempt + 1)
                if params:
                    logger.debug("Query params: %s", params)
                if json_data:
                    logger.debug("Request body: %s", json_data)

                response = self.session.request(
                    method=method,
                    url=url,
                    headers=headers,
                    params=params,
                    json=json_data,
                    timeout=30,
                )

                # Log response
                logger.info("API Response: %s %s -> %d", method, endpoint, response.status_code)

                # Handle rate limiting (with separate retry limit)
                if response.status_code == 429:
                    rate_limit_retries += 1
                    if rate_limit_retries > self.MAX_RATE_LIMIT_RETRIES:
                        raise KalshiAPIError(
                            "Max rate limit retries exceeded",
                            status_code=429
                        )
                    retry_after = int(response.headers.get("Retry-After", 5))
                    logger.warning("Rate limited. Waiting %d seconds. (retry %d/%d)",
                                   retry_after, rate_limit_retries, self.MAX_RATE_LIMIT_RETRIES)
                    time.sleep(retry_after)
                    continue

                # Handle retryable server errors
                if response.status_code in self.RETRY_STATUS_CODES:
                    wait_time = self.RETRY_BACKOFF_BASE * (2 ** attempt)
                    logger.warning(
                        "Server error %d. Retrying in %.1f seconds.",
                        response.status_code,
                        wait_time
                    )
                    time.sleep(wait_time)
                    continue

                # Handle authentication errors (don't retry)
                if response.status_code == 401:
                    raise KalshiAPIError(
                        "Authentication failed. Check your API credentials.",
                        status_code=401
                    )

                # Handle other client errors (don't retry)
                if 400 <= response.status_code < 500:
                    error_body = self._parse_error_response(response)
                    raise KalshiAPIError(
                        error_body.get("message", f"Client error: {response.status_code}"),
                        status_code=response.status_code,
                        response_body=error_body
                    )

                # Success
                if response.status_code == 204:
                    return {}  # No content

                return response.json()

            except requests.exceptions.RequestException as e:
                last_exception = e
                wait_time = self.RETRY_BACKOFF_BASE * (2 ** attempt)
                logger.warning("Request failed: %s. Retrying in %.1f seconds.", e, wait_time)
                time.sleep(wait_time)

        # Max retries exceeded
        response_obj = getattr(last_exception, 'response', None)
        status_code = getattr(response_obj, 'status_code', None) if response_obj else None
        raise KalshiAPIError(
            f"Max retries exceeded. Last error: {last_exception}",
            status_code=status_code
        )

    def _parse_error_response(self, response: requests.Response) -> dict:
        """Parse error response body."""
        try:
            data = response.json()
            # Handle nested error format: {"error": {"code": ..., "message": ..., "details": ...}}
            if "error" in data and isinstance(data["error"], dict):
                error = data["error"]
                # Combine message and details for better error info
                msg = error.get("message", "Unknown error")
                details = error.get("details", "")
                if details:
                    data["message"] = f"{msg}: {details}"
                else:
                    data["message"] = msg
            return data
        except ValueError:
            return {"message": response.text or "Unknown error"}

    # -------------------------------------------------------------------------
    # Account Methods
    # -------------------------------------------------------------------------

    def get_balance(self) -> dict:
        """
        Get account balance.

        Returns:
            dict with balance information including:
            - balance: current cash balance in cents
            - portfolio_value: value of open positions in cents
        """
        return self._make_request("GET", "/portfolio/balance")

    # -------------------------------------------------------------------------
    # Position Methods
    # -------------------------------------------------------------------------

    def get_positions(self, limit: int = 100, cursor: Optional[str] = None) -> dict:
        """
        Get current open positions.

        Args:
            limit: Maximum number of positions to return (default 100)
            cursor: Pagination cursor for next page

        Returns:
            dict with:
            - positions: list of position objects
            - cursor: pagination cursor for next page
        """
        params = {"limit": limit}
        if cursor:
            params["cursor"] = cursor

        return self._make_request("GET", "/portfolio/positions", params=params)

    # -------------------------------------------------------------------------
    # Market Methods
    # -------------------------------------------------------------------------

    def get_markets(
        self,
        limit: int = 100,
        cursor: Optional[str] = None,
        event_ticker: Optional[str] = None,
        series_ticker: Optional[str] = None,
        status: Optional[str] = None,
    ) -> dict:
        """
        Get available markets.

        Args:
            limit: Maximum number of markets to return
            cursor: Pagination cursor
            event_ticker: Filter by event ticker
            series_ticker: Filter by series ticker
            status: Filter by market status (open, closed, settled)

        Returns:
            dict with:
            - markets: list of market objects
            - cursor: pagination cursor
        """
        params = {"limit": limit}
        if cursor:
            params["cursor"] = cursor
        if event_ticker:
            params["event_ticker"] = event_ticker
        if series_ticker:
            params["series_ticker"] = series_ticker
        if status:
            params["status"] = status

        return self._make_request("GET", "/markets", params=params)

    def get_market(self, ticker: str) -> dict:
        """
        Get details for a specific market.

        Args:
            ticker: Market ticker

        Returns:
            dict with market details
        """
        return self._make_request("GET", f"/markets/{ticker}")

    # -------------------------------------------------------------------------
    # Historical Methods
    # -------------------------------------------------------------------------

    def get_historical_cutoff(self) -> dict:
        """Return the live/historical boundary timestamps.

        Endpoint: GET /historical/cutoff
        Returns: {"live_cutoff_ts": int, "historical_cutoff_ts": int}
        """
        return self._make_request("GET", "/historical/cutoff")

    def get_historical_markets(
        self,
        limit: int = 1000,
        cursor: Optional[str] = None,
        series_ticker: Optional[str] = None,
        event_ticker: Optional[str] = None,
        tickers: Optional[list] = None,
    ) -> dict:
        """Fetch markets older than the historical cutoff.

        Endpoint: GET /historical/markets
        Returns: {"markets": [...], "cursor": str}
        """
        params: dict = {"limit": limit}
        if cursor:
            params["cursor"] = cursor
        if series_ticker:
            params["series_ticker"] = series_ticker
        if event_ticker:
            params["event_ticker"] = event_ticker
        if tickers:
            params["tickers"] = ",".join(tickers)
        return self._make_request("GET", "/historical/markets", params=params)

    def get_market_candlesticks(
        self,
        ticker: str,
        period_interval: int = 1440,
        start_ts: Optional[int] = None,
        end_ts: Optional[int] = None,
        historical: bool = False,
    ) -> dict:
        """Fetch OHLC candlesticks for a single market.

        historical=False → GET /markets/{ticker}/candlesticks
        historical=True  → GET /historical/markets/{ticker}/candlesticks
        period_interval: 1 (minute), 60 (hour), 1440 (day).
        Returns: {"candlesticks": [...]}
        """
        if historical:
            endpoint = f"/historical/markets/{ticker}/candlesticks"
        else:
            endpoint = f"/markets/{ticker}/candlesticks"
        params: dict = {"period_interval": period_interval}
        if start_ts is not None:
            params["start_ts"] = start_ts
        if end_ts is not None:
            params["end_ts"] = end_ts
        return self._make_request("GET", endpoint, params=params)

    def get_batch_candlesticks(
        self,
        tickers: list,
        period_interval: int = 1440,
        start_ts: Optional[int] = None,
        end_ts: Optional[int] = None,
    ) -> dict:
        """Fetch OHLC candlesticks for up to 100 live tickers in one call.

        Endpoint: GET /markets/candlesticks
        tickers passed as comma-separated query param.
        Only works for live (non-historical) markets.
        Returns: {"candlesticks": {ticker: [...]}}
        """
        if not tickers:
            raise KalshiAPIError("tickers list must not be empty")
        params: dict = {
            "tickers": ",".join(tickers),
            "period_interval": period_interval,
        }
        if start_ts is not None:
            params["start_ts"] = start_ts
        if end_ts is not None:
            params["end_ts"] = end_ts
        return self._make_request("GET", "/markets/candlesticks", params=params)

    # -------------------------------------------------------------------------
    # Order Methods
    # -------------------------------------------------------------------------

    def place_order(
        self,
        ticker: str,
        side: str,
        quantity: int,
        action: str = "buy",
        order_type: str = "market",
        price: Optional[int] = None,
        client_order_id: Optional[str] = None,
        expiration_ts: Optional[int] = None,
    ) -> dict:
        """
        Place an order.

        Args:
            ticker: Market ticker
            side: "yes" or "no" (which side of the contract)
            quantity: Number of contracts (must be positive)
            action: "buy" or "sell" (default "buy")
            order_type: "market" or "limit"
            price: Price in cents (required for limit orders, 1-99)
            client_order_id: Optional client-specified order ID
            expiration_ts: Optional expiration timestamp (Unix seconds)

        Returns:
            dict with order details including order_id

        Raises:
            KalshiAPIError: If order placement fails or validation fails
        """
        # Validate side
        if side not in ("yes", "no"):
            raise KalshiAPIError("Side must be 'yes' or 'no'")

        # Validate action
        if action not in ("buy", "sell"):
            raise KalshiAPIError("Action must be 'buy' or 'sell'")

        # Validate quantity
        if not isinstance(quantity, int) or quantity <= 0:
            raise KalshiAPIError("Quantity must be a positive integer")

        # Validate order type
        if order_type not in ("market", "limit"):
            raise KalshiAPIError("Order type must be 'market' or 'limit'")

        # Validate price for limit orders
        if order_type == "limit":
            if price is None:
                raise KalshiAPIError("Price is required for limit orders")
            if not isinstance(price, int) or price < 1 or price > 99:
                raise KalshiAPIError("Price must be an integer between 1 and 99 cents")

        # Build order payload
        order_data = {
            "ticker": ticker,
            "action": action,
            "side": side,
            "count": quantity,
            "type": order_type,
        }

        # For market orders, use aggressive price to ensure execution
        if order_type == "market" and price is None:
            # Buy: willing to pay up to 99c, Sell: willing to accept down to 1c
            price = 99 if action == "buy" else 1

        if price is not None:
            # Convert price to yes_price format expected by API
            order_data["yes_price"] = price if side == "yes" else (100 - price)

        if client_order_id:
            order_data["client_order_id"] = client_order_id

        if expiration_ts:
            order_data["expiration_ts"] = expiration_ts

        return self._make_request("POST", "/portfolio/orders", json_data=order_data)

    def cancel_order(self, order_id: str) -> dict:
        """
        Cancel a pending order.

        Args:
            order_id: The order ID to cancel

        Returns:
            dict with cancelled order details
        """
        return self._make_request("DELETE", f"/portfolio/orders/{order_id}")

    def get_order(self, order_id: str) -> dict:
        """
        Get status of a specific order.

        Args:
            order_id: The order ID to look up

        Returns:
            dict with order details including status
        """
        return self._make_request("GET", f"/portfolio/orders/{order_id}")

    def get_orders(
        self,
        ticker: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 100,
        cursor: Optional[str] = None,
    ) -> dict:
        """
        Get orders with optional filters.

        Args:
            ticker: Filter by market ticker
            status: Filter by status (resting, canceled, executed)
            limit: Maximum number of orders to return
            cursor: Pagination cursor

        Returns:
            dict with:
            - orders: list of order objects
            - cursor: pagination cursor
        """
        params = {"limit": limit}
        if ticker:
            params["ticker"] = ticker
        if status:
            params["status"] = status
        if cursor:
            params["cursor"] = cursor

        return self._make_request("GET", "/portfolio/orders", params=params)

    # -------------------------------------------------------------------------
    # Fill Methods
    # -------------------------------------------------------------------------

    def get_fills(
        self,
        ticker: Optional[str] = None,
        order_id: Optional[str] = None,
        limit: int = 100,
        cursor: Optional[str] = None,
    ) -> dict:
        """
        Get fill history.

        Args:
            ticker: Filter by market ticker
            order_id: Filter by order ID
            limit: Maximum number of fills to return
            cursor: Pagination cursor

        Returns:
            dict with:
            - fills: list of fill objects
            - cursor: pagination cursor
        """
        params = {"limit": limit}
        if ticker:
            params["ticker"] = ticker
        if order_id:
            params["order_id"] = order_id
        if cursor:
            params["cursor"] = cursor

        return self._make_request("GET", "/portfolio/fills", params=params)

    # -------------------------------------------------------------------------
    # Settlement Methods
    # -------------------------------------------------------------------------

    def get_settlements(
        self,
        limit: int = 100,
        cursor: Optional[str] = None,
    ) -> dict:
        """
        Get settlement history for settled positions.

        Args:
            limit: Maximum number of settlements to return
            cursor: Pagination cursor

        Returns:
            dict with:
            - settlements: list of settlement objects with revenue, costs, fees
            - cursor: pagination cursor
        """
        params = {"limit": limit}
        if cursor:
            params["cursor"] = cursor

        return self._make_request("GET", "/portfolio/settlements", params=params)
