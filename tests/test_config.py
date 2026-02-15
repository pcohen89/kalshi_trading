# test_config.py - Test configuration loading (Task 7)
"""
Tests for config.py — configuration management module.

Tests cover:
- _get_required: env var retrieval with validation
- _get_optional: env var retrieval with defaults
- get_config: full config loading and validation
- Convenience functions: get_api_credentials, get_api_base_url, etc.
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from unittest.mock import patch

from config import (
    ConfigurationError,
    _get_required,
    _get_optional,
    get_config,
    validate_config,
    get_api_credentials,
    get_api_base_url,
    get_environment,
    get_log_level,
    is_production,
    API_URLS,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

# Minimal valid env vars needed for get_config to succeed
VALID_ENV = {
    "KALSHI_API_KEY": "test_key_abc123",
    "KALSHI_API_SECRET": "test_secret_xyz789",
}

VALID_ENV_PRODUCTION = {
    **VALID_ENV,
    "KALSHI_ENVIRONMENT": "production",
}


# ---------------------------------------------------------------------------
# TestGetRequired
# ---------------------------------------------------------------------------

class TestGetRequired:
    """Tests for the _get_required helper function."""

    @patch.dict(os.environ, {"KALSHI_API_KEY": "real_key_value"}, clear=True)
    def test_returns_value_when_set(self):
        """_get_required returns the env var value when it is set."""
        result = _get_required("KALSHI_API_KEY")
        assert result == "real_key_value"

    @patch.dict(os.environ, {}, clear=True)
    def test_raises_when_missing(self):
        """_get_required raises ConfigurationError when the key is not set."""
        with pytest.raises(ConfigurationError, match="Missing required configuration: KALSHI_API_KEY"):
            _get_required("KALSHI_API_KEY")

    @patch.dict(os.environ, {"KALSHI_API_KEY": ""}, clear=True)
    def test_raises_when_empty(self):
        """_get_required raises ConfigurationError when the value is empty string."""
        with pytest.raises(ConfigurationError, match="Missing required configuration: KALSHI_API_KEY"):
            _get_required("KALSHI_API_KEY")

    @patch.dict(os.environ, {"KALSHI_API_KEY": "your_api_key_here"}, clear=True)
    def test_raises_when_placeholder(self):
        """_get_required raises ConfigurationError when value starts with 'your_'."""
        with pytest.raises(ConfigurationError, match="Missing required configuration: KALSHI_API_KEY"):
            _get_required("KALSHI_API_KEY")


# ---------------------------------------------------------------------------
# TestGetOptional
# ---------------------------------------------------------------------------

class TestGetOptional:
    """Tests for the _get_optional helper function."""

    @patch.dict(os.environ, {"LOG_LEVEL": "DEBUG"}, clear=True)
    def test_returns_value_when_set(self):
        """_get_optional returns the env var value when it is set."""
        result = _get_optional("LOG_LEVEL", "INFO")
        assert result == "DEBUG"

    @patch.dict(os.environ, {}, clear=True)
    def test_returns_default_when_missing(self):
        """_get_optional returns the default when the key is not set."""
        result = _get_optional("LOG_LEVEL", "INFO")
        assert result == "INFO"


# ---------------------------------------------------------------------------
# TestGetConfig
# ---------------------------------------------------------------------------

class TestGetConfig:
    """Tests for the get_config function."""

    @patch.dict(os.environ, VALID_ENV, clear=True)
    def test_valid_config_returns_all_keys(self):
        """get_config returns a dict with all expected keys."""
        config = get_config()
        assert "api_key" in config
        assert "api_secret" in config
        assert "environment" in config
        assert "log_level" in config
        assert "api_base_url" in config
        assert config["api_key"] == "test_key_abc123"
        assert config["api_secret"] == "test_secret_xyz789"

    @patch.dict(os.environ, {"KALSHI_API_SECRET": "test_secret"}, clear=True)
    def test_missing_api_key_raises(self):
        """get_config raises ConfigurationError when KALSHI_API_KEY is missing."""
        with pytest.raises(ConfigurationError, match="KALSHI_API_KEY"):
            get_config()

    @patch.dict(os.environ, {"KALSHI_API_KEY": "test_key"}, clear=True)
    def test_missing_api_secret_raises(self):
        """get_config raises ConfigurationError when KALSHI_API_SECRET is missing."""
        with pytest.raises(ConfigurationError, match="KALSHI_API_SECRET"):
            get_config()

    @patch.dict(os.environ, {**VALID_ENV, "KALSHI_ENVIRONMENT": "staging"}, clear=True)
    def test_invalid_environment_raises(self):
        """get_config raises ConfigurationError for an unrecognised environment."""
        with pytest.raises(ConfigurationError, match="Invalid KALSHI_ENVIRONMENT"):
            get_config()

    @patch.dict(os.environ, {**VALID_ENV, "LOG_LEVEL": "TRACE"}, clear=True)
    def test_invalid_log_level_raises(self):
        """get_config raises ConfigurationError for an invalid log level."""
        with pytest.raises(ConfigurationError, match="Invalid LOG_LEVEL"):
            get_config()

    @patch.dict(os.environ, VALID_ENV, clear=True)
    def test_defaults_to_sandbox(self):
        """get_config defaults to sandbox environment when KALSHI_ENVIRONMENT is not set."""
        config = get_config()
        assert config["environment"] == "sandbox"
        assert config["api_base_url"] == API_URLS["sandbox"]

    @patch.dict(os.environ, VALID_ENV, clear=True)
    def test_defaults_to_info_log_level(self):
        """get_config defaults to INFO log level when LOG_LEVEL is not set."""
        config = get_config()
        assert config["log_level"] == "INFO"

    @patch.dict(os.environ, VALID_ENV_PRODUCTION, clear=True)
    def test_production_environment(self):
        """get_config correctly loads production environment and URL."""
        config = get_config()
        assert config["environment"] == "production"
        assert config["api_base_url"] == API_URLS["production"]


# ---------------------------------------------------------------------------
# TestConvenienceFunctions
# ---------------------------------------------------------------------------

class TestConvenienceFunctions:
    """Tests for convenience wrapper functions."""

    @patch.dict(os.environ, VALID_ENV, clear=True)
    def test_get_api_credentials_returns_tuple(self):
        """get_api_credentials returns a (key, secret) tuple."""
        key, secret = get_api_credentials()
        assert key == "test_key_abc123"
        assert secret == "test_secret_xyz789"

    @patch.dict(os.environ, VALID_ENV, clear=True)
    def test_get_api_base_url_returns_string(self):
        """get_api_base_url returns the base URL string for the configured env."""
        url = get_api_base_url()
        assert isinstance(url, str)
        assert url == API_URLS["sandbox"]

    @patch.dict(os.environ, VALID_ENV, clear=True)
    def test_get_environment_returns_string(self):
        """get_environment returns the environment name as a string."""
        env = get_environment()
        assert isinstance(env, str)
        assert env == "sandbox"

    @patch.dict(os.environ, VALID_ENV, clear=True)
    def test_get_log_level_returns_string(self):
        """get_log_level returns the log level as a string."""
        level = get_log_level()
        assert isinstance(level, str)
        assert level == "INFO"

    @patch.dict(os.environ, VALID_ENV_PRODUCTION, clear=True)
    def test_is_production_true(self):
        """is_production returns True when environment is production."""
        assert is_production() is True

    @patch.dict(os.environ, VALID_ENV, clear=True)
    def test_is_production_false(self):
        """is_production returns False when environment is sandbox."""
        assert is_production() is False

    @patch.dict(os.environ, VALID_ENV, clear=True)
    def test_validate_config_returns_true(self):
        """validate_config returns True when configuration is valid."""
        assert validate_config() is True
