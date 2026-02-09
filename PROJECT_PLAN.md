# Kalshi Trading System - V1 Project Plan

## Project Overview

### Objective
Build a minimal viable trading infrastructure for Kalshi that can connect to the API, execute trades programmatically, and track basic performance. This is a foundational version focused on core functionality - strategy development and optimization will come in future iterations.

### Success Criteria
- Successfully authenticate and connect to Kalshi API
- Execute buy and sell orders programmatically
- Track open positions and calculate basic P&L
- Log all trades and activities
- Provide simple manual controls for trading decisions

### Out of Scope for V1
- Automated trading strategies/algorithms
- Historical data collection and storage
- Market analysis and signal generation
- Advanced risk management systems
- Backtesting framework
- Performance optimization
- Complex monitoring dashboards

---

## Current Progress

### Completed Tasks

#### Task 5: Basic Configuration & Setup ✅
**Status**: Complete
**Date**: January 2025

**What was implemented**:
- `config.py` - Full configuration loader with validation
- `.env.example` - Template with all environment variables
- `.env` - User has created this with their Kalshi API credentials
- `requirements.txt` - Dependencies (requests, python-dotenv, pytest)
- `README.md` - Complete setup instructions
- `.gitignore` - Prevents credentials and logs from being committed

**Key features of config.py**:
- Loads credentials from `.env` file using python-dotenv
- Validates required config exists, raises `ConfigurationError` if missing
- Supports two environments with different API URLs:
  - Sandbox: `https://demo-api.kalshi.co/trade-api/v2`
  - Production: `https://api.elections.kalshi.com/trade-api/v2`
- Convenience functions: `get_config()`, `get_api_credentials()`, `get_api_base_url()`, `is_production()`

**How to use config.py**:
```python
from config import get_config, get_api_credentials, get_api_base_url

# Get all config as dict
config = get_config()

# Get just credentials
api_key, api_secret = get_api_credentials()

# Get API URL for current environment
base_url = get_api_base_url()
```

**Environment setup**:
- User has installed dependencies: `pip install -r requirements.txt`
- User has created `.env` with valid Kalshi API credentials
- Environment is set to `production` (user's preference)
- Repository is initialized with git and pushed to GitHub

---

#### Task 1: Kalshi API Integration ✅
**Status**: Complete
**Date**: February 2025

**What was implemented**:
- `kalshi_client.py` - Full API client (521 lines) with all required methods
- `tests/test_api_client.py` - Comprehensive test suite (24 tests)
- `pytest.ini` - Test configuration with custom markers
- `requirements.txt` - Added `cryptography>=41.0.0` for RSA signing
- `.gitignore` - Added `*.pem` to protect private keys
- `.env.example` - Updated with .pem file path instructions
- `kalshi_private_key.pem` - Template file for user's private key

**KalshiClient class features**:
- RSA-PSS request signing (per Kalshi API v2 spec)
- Automatic retry with exponential backoff (3 retries for 5xx errors)
- Rate limit handling (429) with separate retry limit (5 retries)
- Comprehensive error handling with `KalshiAPIError` exception
- Request/response logging at INFO level
- Session reuse for connection efficiency

**Available methods**:
```python
from kalshi_client import KalshiClient

client = KalshiClient()

# Account
client.get_balance()  # Returns: {balance, portfolio_value} in cents

# Positions
client.get_positions(limit=100, cursor=None)

# Markets
client.get_markets(limit=100, cursor=None, event_ticker=None, status=None)
client.get_market(ticker)

# Orders
client.place_order(ticker, side, quantity, action="buy", order_type="market", price=None)
client.cancel_order(order_id)
client.get_order(order_id)
client.get_orders(ticker=None, status=None, limit=100)

# Fills
client.get_fills(ticker=None, order_id=None, limit=100)
```

**Order placement notes**:
- `side`: "yes" or "no"
- `action`: "buy" or "sell" (to close positions)
- `order_type`: "market" or "limit"
- `price`: Required for limit orders, must be 1-99 cents
- `quantity`: Must be positive integer

**Private key setup**:
The API secret must be stored as a `.pem` file (not inline in `.env`):
1. Save private key to `kalshi_private_key.pem`
2. Set `KALSHI_API_SECRET=./kalshi_private_key.pem` in `.env`

**Test results**:
- 18 unit tests (mocked) - all pass
- 6 integration tests (live API) - all pass
- Run unit tests: `pytest tests/test_api_client.py -m "not integration"`
- Run integration tests: `pytest tests/test_api_client.py -m integration`
- Run all: `pytest tests/test_api_client.py -v`

**Important API notes**:
- Production URL changed to `https://api.elections.kalshi.com/trade-api/v2`
- All monetary values are in cents (divide by 100 for dollars)
- Timestamps are Unix milliseconds for authentication

---

#### Task 2: Simple Trade Execution Interface ✅
**Status**: Complete
**Date**: February 2025

**What was implemented**:
- `trade_executor.py` - Trade execution wrapper (250 lines)
- `cli_interface.py` - Interactive CLI interface (420 lines)
- `tests/test_trade_executor.py` - Comprehensive test suite (40 tests)

**TradeExecutor class features**:
- Wrapper around KalshiClient for common operations
- Input validation (side, quantity, price)
- `TradeExecutionError` exception for clean error handling
- Market search across 24 popular series with deduplication

**Available methods**:
```python
from trade_executor import TradeExecutor

executor = TradeExecutor()

# Order placement
executor.place_market_order(ticker, side, quantity)
executor.place_limit_order(ticker, side, quantity, price)

# Order management
executor.cancel_order(order_id)
executor.get_order_status(order_id)
executor.list_open_orders()

# Market discovery
executor.search_markets(query="bitcoin", status="open", limit=20)
executor.get_market_info(ticker)
executor.validate_ticker(ticker)
```

**CLI Interface features**:
- Menu-driven interface with 7 options
- Market search across popular series (crypto, politics, sports, entertainment)
- Prompts for series ticker if search finds no results
- Order confirmation before submission
- Clear display of market info, prices, and order status

**CLI Menu**:
```
1. Search markets
2. Place market order
3. Place limit order
4. View open orders
5. Cancel an order
6. Check order status
7. Exit
```

**To run the CLI**:
```bash
cd kalshi_trading
python3 cli_interface.py
```

**Test results**:
- 40 unit tests (mocked) - all pass
- Run tests: `pytest tests/test_trade_executor.py -v`

**Bug fixes during implementation**:
- Fixed API error parsing for nested error format
- Fixed market order price requirement (API requires price even for market orders)
- Added aggressive pricing for market orders to ensure execution

---

#### Task 3: Portfolio & Position Tracking ⏳
**Status**: Mostly complete — needs sold position tracking before closing out
**Date**: February 2026

**What was implemented**:
- `portfolio_tracker.py` - Full portfolio tracker (280 lines)
- `tests/test_portfolio.py` - Comprehensive test suite (48 tests)
- Added `get_settlements()` to `kalshi_client.py` for realized P&L

**PortfolioTracker class features**:
- Paginated fetching of positions, fills, and settlements
- Midpoint pricing for mark-to-market (bid/ask midpoint, falls back to last_price)
- Settled market handling (100c for winners, 0c for losers)
- Graceful degradation — skips positions that fail price lookup
- Formatted portfolio summary display matching CLI conventions

**Available methods**:
```python
from portfolio_tracker import PortfolioTracker

tracker = PortfolioTracker()

# Positions
tracker.get_current_positions()        # Open positions (non-zero only)
tracker.calculate_position_pnl(pos)    # Unrealized P&L for one position
tracker.calculate_total_pnl()          # Aggregate unrealized P&L

# Realized P&L
tracker.get_realized_pnl()             # From /portfolio/settlements endpoint

# Display
tracker.display_portfolio_summary()    # Formatted summary to stdout
```

**Key API discovery**:
- `/portfolio/positions` does NOT include settled/finalized markets
- Must use `/portfolio/settlements` for realized P&L (revenue, cost, fees)
- `fee_cost` in settlements is a dollar string (e.g. "0.0900"), not cents

**Test results**:
- 48 unit tests (mocked) - all pass
- Run tests: `pytest tests/test_portfolio.py -v`

**Remaining before closing out Task 3**:
- Realized P&L currently only captures settlements (markets that expired/resolved)
- Need to also capture P&L from positions that were manually sold (closed via sell orders)
- Sold positions generate fills but may not appear in settlements until the market itself settles
- Should incorporate fill-based P&L for sold positions alongside settlement-based P&L

---

### Next Task: Task 4 - Trade Logging & History

**Start here**: Implement `trade_logger.py`.

**Prerequisites are ready**:
- ✅ `KalshiClient` provides `get_fills()`, `get_orders()`
- ✅ `PortfolioTracker` provides position and P&L data
- ✅ Authentication and error handling working

**Files to implement**:
- `trade_logger.py` - Trade logging and history

---

## System Architecture

### High-Level Components
1. **API Integration Layer** - Connect to Kalshi platform
2. **Order Execution Module** - Place and manage orders
3. **Portfolio Tracker** - Monitor positions and calculate P&L
4. **Basic Logging** - Record all trades and system events
5. **Configuration Manager** - Store credentials and settings

---

## Task Breakdown

### Task 1: Kalshi API Integration

**Objective**: Establish secure connection to Kalshi API and implement core API functions needed for trading.

**Inputs**:
- Kalshi API credentials (API key, secret)
- Kalshi API documentation (https://trading-api.readme.io/reference/getting-started)
- Environment configuration (production vs sandbox)

**Outputs**:
- `kalshi_client.py` - Python class with methods for:
  - Authentication (login, token refresh)
  - Get account balance
  - Get current positions
  - Get available markets (basic info only)
  - Place order (market and limit)
  - Cancel order
  - Get order status
  - Get fill history
- `config.py` - Configuration management:
  - Load API credentials from environment variables
  - API endpoint URLs (prod vs sandbox)
  - Basic settings (timeout, retry count)
- Basic error handling and logging

**Technical Requirements**:
- Use `requests` library for HTTP calls
- Store credentials in environment variables (never hardcode)
- Implement basic retry logic for failed requests
- Log all API requests and responses at INFO level
- Handle common errors (401 Unauthorized, 429 Rate Limit, 500 Server Error)

**Success Criteria**:
- Successfully authenticate and receive auth token
- Can retrieve account balance
- Can fetch list of available markets
- Can retrieve current positions
- All API methods have error handling
- Credentials are never exposed in logs or code

---

### Task 2: Simple Trade Execution Interface

**Objective**: Create a simple command-line interface for manually executing trades through code.

**Inputs**:
- Market ticker or event ID (from user input)
- Trade direction: "yes" or "no" (buy yes contracts or buy no contracts)
- Quantity (number of contracts)
- Order type: "market" or "limit"
- Price in cents (for limit orders only, e.g., 52 for $0.52)

**Outputs**:
- `trade_executor.py` - Core execution functions:
  - `place_market_order(ticker, side, quantity)` - Submit market order
  - `place_limit_order(ticker, side, quantity, price)` - Submit limit order
  - `cancel_order(order_id)` - Cancel pending order
  - `get_order_status(order_id)` - Check if filled/pending/cancelled
  - `list_open_orders()` - Show all pending orders
- `cli_interface.py` - Simple command-line interface:
  - Interactive prompts for trade parameters
  - Display order confirmation before submission
  - Show order ID after successful submission
  - Option to view open orders
  - Option to cancel orders
- Basic input validation (positive quantities, valid prices, etc.)

**Technical Requirements**:
- Use Python `input()` for CLI interaction
- Validate all user inputs before API calls
- Clear confirmation messages before placing orders
- Display order details after execution
- Handle and display API errors gracefully

**Success Criteria**:
- Can place market orders through CLI
- Can place limit orders with specified price
- Orders successfully appear in Kalshi account
- Can cancel pending orders
- Input validation prevents invalid orders
- Clear error messages for failed orders

---

### Task 3: Portfolio & Position Tracking

**Objective**: Track all open positions and calculate profit/loss in real-time.

**Inputs**:
- Current positions from Kalshi API
- Fill history from Kalshi API
- Current market prices for open positions

**Outputs**:
- `portfolio_tracker.py` - Position tracking logic:
  - `get_current_positions()` - Fetch all open positions from API
  - `calculate_position_pnl(position)` - Calculate unrealized P&L for one position
  - `calculate_total_pnl()` - Calculate total unrealized P&L across all positions
  - `get_realized_pnl()` - Calculate realized P&L from closed positions
  - `display_portfolio_summary()` - Print formatted portfolio overview
- Portfolio summary display:
  - List of open positions with quantities and entry prices
  - Current market value of each position
  - Unrealized P&L per position
  - Total unrealized P&L
  - Account balance
  - Total portfolio value
- Simple position data structures (could be dict or dataclass)

**Technical Requirements**:
- Fetch positions in real-time from API (no local caching for V1)
- Calculate P&L correctly accounting for yes/no positions
- Handle positions that have been partially filled
- Format output to be human-readable
- Handle edge cases (no positions, API errors)

**Success Criteria**:
- Positions displayed match Kalshi account
- P&L calculations are accurate
- Can track multiple simultaneous positions
- Summary updates when refreshed
- Clear display format showing all relevant information

---

### Task 4: Trade Logging & History

**Objective**: Record all trading activity for audit trail and basic performance review.

**Inputs**:
- Order submissions (timestamp, ticker, side, quantity, price, order_id)
- Order fills (timestamp, order_id, fill_price, quantity_filled)
- Order cancellations (timestamp, order_id)
- Errors and exceptions

**Outputs**:
- `trade_logger.py` - Logging functionality:
  - `log_order_submission(order_details)` - Record when order is placed
  - `log_order_fill(fill_details)` - Record when order fills
  - `log_order_cancellation(order_id)` - Record cancellations
  - `log_error(error_message)` - Record errors
  - `get_trade_history(start_date, end_date)` - Retrieve historical trades
- Log file structure:
  - `trades.log` - All trading activity with timestamps
  - `errors.log` - Errors and exceptions
- CSV export of trade history:
  - `export_trades_to_csv(filename)` - Export all trades to CSV
- Simple log viewer function to display recent trades

**Technical Requirements**:
- Use Python `logging` module
- Structured log format with timestamps
- Separate files for trades and errors
- Log rotation to prevent huge files (e.g., daily rotation)
- CSV export with headers for easy analysis in Excel

**Success Criteria**:
- Every order submission is logged
- Every fill is logged with execution price
- Logs are human-readable
- Can export trade history to CSV
- Log files don't consume excessive disk space
- Timestamps are accurate and timezone-aware

---

### Task 5: Basic Configuration & Setup

**Objective**: Centralize configuration and create easy setup process.

**Inputs**:
- API credentials
- Environment selection (production vs sandbox)
- Basic preferences (log level, default order sizes)

**Outputs**:
- `.env.example` - Template showing required environment variables:
  ```
  KALSHI_API_KEY=your_api_key_here
  KALSHI_API_SECRET=your_secret_here
  KALSHI_ENVIRONMENT=sandbox  # or production
  LOG_LEVEL=INFO
  ```
- `config.py` - Configuration loader:
  - Load environment variables
  - Validate required config exists
  - Provide defaults for optional config
  - Environment-specific settings (different API URLs)
- `setup.py` or `requirements.txt` - Python dependencies:
  - requests
  - python-dotenv (for .env file loading)
  - Any other required packages
- `README.md` - Setup instructions:
  - How to install dependencies
  - How to set up API credentials
  - How to run the trading interface
  - Basic usage examples

**Technical Requirements**:
- Use `python-dotenv` to load .env files
- Never commit actual credentials to version control
- Validate that all required config is present at startup
- Provide clear error messages for missing config
- Document all configuration options

**Success Criteria**:
- Can set up environment in < 15 minutes
- Clear error if credentials are missing
- Easy to switch between sandbox and production
- README provides complete setup instructions
- No credentials stored in code

---

### Task 6: Main Application Entry Point

**Objective**: Create a simple main script that ties everything together.

**Inputs**:
- Configuration from environment
- User commands from CLI

**Outputs**:
- `main.py` - Main application script:
  - Initialize API client with credentials
  - Display main menu with options:
    1. View portfolio summary
    2. Place a trade
    3. View open orders
    4. Cancel an order
    5. View recent trade history
    6. Exit
  - Handle menu navigation
  - Gracefully handle errors and allow retry
  - Clean shutdown
- Simple menu-driven interface for all functionality

**Technical Requirements**:
- Clear, numbered menu options
- Input validation for menu selections
- Error handling that doesn't crash the program
- Ability to return to main menu from any action
- Clean exit with goodbye message

**Success Criteria**:
- Program starts without errors when config is correct
- All menu options work correctly
- Can perform multiple actions without restarting
- Errors don't crash the program
- User-friendly prompts and messages

---

### Task 7: Basic Testing

**Objective**: Test core functionality to ensure reliability.

**Inputs**:
- Implemented modules
- Test API credentials (sandbox environment)
- Test scenarios

**Outputs**:
- `tests/` directory:
  - `test_api_client.py` - Test API integration
    - Test authentication
    - Test getting balance
    - Test placing orders (in sandbox)
    - Test error handling
  - `test_portfolio.py` - Test P&L calculations
    - Test position P&L calculation
    - Test portfolio summary
  - `test_config.py` - Test configuration loading
- Manual test checklist:
  - Place market order (sandbox)
  - Place limit order (sandbox)
  - Cancel order (sandbox)
  - View positions
  - Check logs are created

**Technical Requirements**:
- Use pytest for automated tests
- Tests should run against sandbox environment only
- Mock API responses where appropriate
- Don't require production credentials to run tests

**Success Criteria**:
- All automated tests pass
- Manual test checklist can be completed successfully
- No critical bugs in core functionality
- Error handling works as expected

---

## Technology Stack

### Core Technologies
- **Language**: Python 3.9+
- **HTTP Client**: requests library
- **Configuration**: python-dotenv
- **Testing**: pytest (for basic tests)
- **Logging**: Python logging module

### No Database Required for V1
- All data fetched from API on-demand
- No local data storage or caching
- Logs stored as simple text files

---

## Project Timeline

### Week 1: Foundation
- **Day 1-2**: Task 1 - API Integration
- **Day 3-4**: Task 5 - Configuration & Setup
- **Day 5**: Task 4 - Trade Logging

### Week 2: Trading Interface
- **Day 1-2**: Task 2 - Trade Execution Interface
- **Day 3-4**: Task 3 - Portfolio Tracking
- **Day 5**: Task 6 - Main Application Entry Point

### Week 3: Testing & Polish
- **Day 1-2**: Task 7 - Basic Testing
- **Day 3-4**: Bug fixes and refinements
- **Day 5**: Documentation and final testing

---

## What's NOT Included in V1

The following will be tackled in future versions:

### Future V2 Features:
- Automated trading strategies
- Historical data collection and database
- Market analysis and signal generation
- Backtesting framework
- Advanced risk management
- Position sizing algorithms
- Portfolio optimization

### Future V3 Features:
- Web dashboard for monitoring
- Automated strategy execution
- Performance analytics and reporting
- Multi-strategy management
- Advanced order types
- Integration with external data sources

---

## Success Metrics for V1

### Functional Requirements
- Can authenticate to Kalshi API ✓
- Can place market orders ✓
- Can place limit orders ✓
- Can cancel orders ✓
- Can view current positions ✓
- Can calculate P&L ✓
- All trades are logged ✓

### Code Quality
- No hardcoded credentials ✓
- Clear error messages ✓
- Basic tests pass ✓
- README explains setup ✓

### User Experience
- Setup time < 15 minutes ✓
- Can complete a trade in < 1 minute ✓
- Clear feedback for all actions ✓
- No unexpected crashes ✓

---

## Risk Considerations for V1

### Technical Risks
- API authentication failures
- Network connectivity issues
- Incorrect order submission

**Mitigation**: 
- Test thoroughly in sandbox environment first
- Clear error messages
- Confirmation before each trade
- Manual intervention for all trades (no automation yet)

### Financial Risks
- Accidental trades due to user error
- Misunderstanding P&L calculations

**Mitigation**:
- Confirmation prompts before placing orders
- Start with small position sizes
- Clear documentation of how P&L is calculated
- Use sandbox environment for initial testing

---

## Next Steps

1. **Set up development environment**
   - Install Python 3.9+
   - Create Kalshi sandbox account
   - Get API credentials

2. **Begin Task 1: API Integration**
   - Read Kalshi API documentation
   - Implement authentication
   - Test basic API calls

3. **Progress through tasks sequentially**
   - Complete each task fully before moving to next
   - Test each component as it's built
   - Document any issues or deviations

4. **Testing in Sandbox**
   - Complete all testing in sandbox environment
   - Verify all functionality works correctly
   - Only move to production after thorough testing

5. **Production Deployment**
   - Start with small position sizes
   - Monitor closely for any issues
   - Keep detailed logs of all activity

---

## Notes for AI Coding Agents

When working on individual tasks from this document:

1. **Read the full task description** before starting implementation
2. **Verify all inputs are available** or request them explicitly
3. **Follow the technical requirements** exactly as specified
4. **Test against success criteria** before marking task complete
5. **Keep it simple** - this is V1, not the final product
6. **Focus on reliability over features** - a few working features is better than many broken ones
7. **Document any assumptions** made during implementation
8. **Ask for clarification** if requirements are unclear
9. **Coordinate with dependent tasks** - some tasks build on others
10. **Remember: No automation yet** - this version is for manual trading only

### Task Dependencies
- Task 2 depends on Task 1 (needs API client)
- Task 3 depends on Task 1 (needs API client)
- Task 4 can be done independently
- Task 5 should be done early (needed by most tasks)
- Task 6 depends on Tasks 1, 2, 3, 4 (integrates everything)
- Task 7 depends on all others (tests everything)

### Code Organization
```
kalshi_trading/
├── .env                    # Environment variables (not in git)
├── .env.example           # Template for .env
├── requirements.txt       # Python dependencies
├── README.md              # Setup and usage instructions
├── config.py              # Configuration management
├── kalshi_client.py       # API integration (Task 1)
├── trade_executor.py      # Order execution (Task 2)
├── portfolio_tracker.py   # Position tracking (Task 3)
├── trade_logger.py        # Logging (Task 4)
├── cli_interface.py       # CLI interface (Task 2)
├── main.py                # Main entry point (Task 6)
├── logs/                  # Log files directory
│   ├── trades.log
│   └── errors.log
└── tests/                 # Test files (Task 7)
    ├── test_api_client.py
    ├── test_portfolio.py
    └── test_config.py
```

This structure keeps the codebase simple and organized for V1.
