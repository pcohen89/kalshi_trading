# config.py - Configuration management (Task 5)
"""
Configuration loader for the Kalshi Trading System.

Loads settings from environment variables (via .env file).
Validates required configuration at import time.
"""

import os
from pathlib import Path
from dotenv import load_dotenv


# Load .env file from the project directory
_env_path = Path(__file__).parent / ".env"
load_dotenv(_env_path)


# API URLs for each environment
API_URLS = {
    "sandbox": "https://demo-api.kalshi.co/trade-api/v2",
    "production": "https://api.elections.kalshi.com/trade-api/v2",
}

# Valid log levels
VALID_LOG_LEVELS = {"DEBUG", "INFO", "WARNING", "ERROR"}


class ConfigurationError(Exception):
    """Raised when required configuration is missing or invalid."""
    pass


def _get_required(key: str) -> str:
    """Get a required environment variable or raise an error."""
    value = os.getenv(key)
    if not value or value.startswith("your_"):
        raise ConfigurationError(
            f"Missing required configuration: {key}\n"
            f"Please set {key} in your .env file.\n"
            f"See .env.example for reference."
        )
    return value


def _get_optional(key: str, default: str) -> str:
    """Get an optional environment variable with a default."""
    return os.getenv(key, default)


def get_config() -> dict:
    """
    Load and validate configuration.

    Returns a dictionary with all configuration values.
    Raises ConfigurationError if required values are missing.
    """
    # Load required values
    api_key = _get_required("KALSHI_API_KEY")
    api_secret = _get_required("KALSHI_API_SECRET")

    # Load optional values with defaults
    environment = _get_optional("KALSHI_ENVIRONMENT", "sandbox").lower()
    log_level = _get_optional("LOG_LEVEL", "INFO").upper()

    # Validate environment
    if environment not in API_URLS:
        raise ConfigurationError(
            f"Invalid KALSHI_ENVIRONMENT: '{environment}'\n"
            f"Must be one of: {', '.join(API_URLS.keys())}"
        )

    # Validate log level
    if log_level not in VALID_LOG_LEVELS:
        raise ConfigurationError(
            f"Invalid LOG_LEVEL: '{log_level}'\n"
            f"Must be one of: {', '.join(VALID_LOG_LEVELS)}"
        )

    return {
        "api_key": api_key,
        "api_secret": api_secret,
        "environment": environment,
        "log_level": log_level,
        "api_base_url": API_URLS[environment],
    }


def validate_config() -> bool:
    """
    Validate configuration without returning values.

    Returns True if valid, raises ConfigurationError if not.
    Useful for startup checks.
    """
    get_config()
    return True


# Convenience functions for accessing individual config values
def get_api_credentials() -> tuple[str, str]:
    """Return (api_key, api_secret) tuple."""
    config = get_config()
    return config["api_key"], config["api_secret"]


def get_api_base_url() -> str:
    """Return the API base URL for the configured environment."""
    config = get_config()
    return config["api_base_url"]


def get_environment() -> str:
    """Return the current environment (sandbox or production)."""
    config = get_config()
    return config["environment"]


def get_log_level() -> str:
    """Return the configured log level."""
    config = get_config()
    return config["log_level"]


def is_production() -> bool:
    """Check if running in production environment."""
    return get_environment() == "production"
