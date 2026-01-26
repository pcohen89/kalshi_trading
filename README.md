# Kalshi Trading System - V1

Minimal viable trading infrastructure for Kalshi prediction markets.

## Prerequisites

- Python 3.9 or higher
- A Kalshi account with API access

## Quick Start

### 1. Clone and navigate to the project

```bash
cd kalshi_trading
```

### 2. Create a virtual environment (recommended)

```bash
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Set up your credentials

Copy the example environment file:

```bash
cp .env.example .env
```

Edit `.env` and add your Kalshi API credentials:

```
KALSHI_API_KEY=your_actual_api_key
KALSHI_API_SECRET=your_actual_api_secret
```

To get your API credentials:
1. Log in to [Kalshi](https://kalshi.com)
2. Go to Account Settings > API
3. Generate a new API key

### 5. Verify your setup

```bash
python -c "from config import validate_config; validate_config(); print('Configuration valid!')"
```

## Configuration Options

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `KALSHI_API_KEY` | Yes | - | Your Kalshi API key |
| `KALSHI_API_SECRET` | Yes | - | Your Kalshi API secret |
| `KALSHI_ENVIRONMENT` | No | `sandbox` | `sandbox` or `production` |
| `LOG_LEVEL` | No | `INFO` | `DEBUG`, `INFO`, `WARNING`, or `ERROR` |

## Environments

- **Sandbox** (default): Use `KALSHI_ENVIRONMENT=sandbox` for testing. This connects to Kalshi's demo API where you can practice without real money.

- **Production**: Use `KALSHI_ENVIRONMENT=production` for live trading with real funds. Be careful!

## Project Structure

```
kalshi_trading/
├── .env.example      # Template for environment variables
├── .env              # Your local configuration (not in git)
├── config.py         # Configuration loader
├── requirements.txt  # Python dependencies
└── README.md         # This file
```

## Usage

Import the configuration in your code:

```python
from config import get_config, get_api_credentials, is_production

# Get all config
config = get_config()
print(f"Using {config['environment']} environment")
print(f"API URL: {config['api_base_url']}")

# Get just credentials
api_key, api_secret = get_api_credentials()

# Check environment
if is_production():
    print("WARNING: Running in production mode!")
```

## Troubleshooting

### "Missing required configuration" error

Make sure you:
1. Copied `.env.example` to `.env`
2. Replaced the placeholder values with your actual credentials
3. Saved the file

### "Invalid KALSHI_ENVIRONMENT" error

Check that `KALSHI_ENVIRONMENT` is set to either `sandbox` or `production` (lowercase).

### Module not found errors

Make sure you:
1. Activated your virtual environment
2. Ran `pip install -r requirements.txt`

## Security Notes

- Never commit your `.env` file to version control
- The `.env` file should already be in `.gitignore`
- Never share your API credentials
- Use the sandbox environment for testing
