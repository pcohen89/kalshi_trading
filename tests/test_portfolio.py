# test_portfolio.py - Unit tests for portfolio tracker (Task 3)
"""
Unit tests for the PortfolioTracker class and helper functions.

These tests use mocked KalshiClient to test position tracking,
P&L calculations, and display output without making real API calls.
"""

import pytest
from unittest.mock import Mock, patch, call

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from portfolio_tracker import (
    PortfolioTracker, PortfolioError,
    _format_dollars, _format_pnl, _print_position_line,
)
from kalshi_client import KalshiAPIError


@pytest.fixture
def mock_client():
    """Create a mock KalshiClient."""
    return Mock()


@pytest.fixture
def tracker(mock_client):
    """Create a PortfolioTracker with a mock client."""
    return PortfolioTracker(client=mock_client)


# =============================================================================
# Helper Function Tests
# =============================================================================

class TestHelperFunctions:
    """Tests for module-level helper functions."""

    def test_format_dollars_positive(self):
        """Formats positive cents to dollars."""
        assert _format_dollars(1234) == "$12.34"

    def test_format_dollars_zero(self):
        """Formats zero cents."""
        assert _format_dollars(0) == "$0.00"

    def test_format_dollars_none(self):
        """Formats None as zero dollars."""
        assert _format_dollars(None) == "$0.00"

    def test_format_dollars_negative(self):
        """Formats negative cents using absolute value."""
        assert _format_dollars(-500) == "$5.00"

    def test_format_pnl_positive(self):
        """Formats positive P&L with plus sign."""
        assert _format_pnl(500) == "+$5.00"

    def test_format_pnl_negative(self):
        """Formats negative P&L with minus sign."""
        assert _format_pnl(-300) == "-$3.00"

    def test_format_pnl_zero(self):
        """Formats zero P&L with plus sign."""
        assert _format_pnl(0) == "+$0.00"

    def test_format_pnl_none(self):
        """Formats None P&L as zero."""
        assert _format_pnl(None) == "+$0.00"


# =============================================================================
# Get Current Positions Tests
# =============================================================================

class TestGetCurrentPositions:
    """Tests for get_current_positions method."""

    def test_returns_only_nonzero_positions(self, tracker, mock_client):
        """Filters out positions with position == 0."""
        mock_client.get_positions.return_value = {
            "market_positions": [
                {"ticker": "A", "position": 5},
                {"ticker": "B", "position": 0},
                {"ticker": "C", "position": -3},
            ],
            "cursor": "",
        }

        result = tracker.get_current_positions()

        assert len(result) == 2
        assert result[0]["ticker"] == "A"
        assert result[1]["ticker"] == "C"

    def test_empty_positions(self, tracker, mock_client):
        """Returns empty list when no positions."""
        mock_client.get_positions.return_value = {
            "market_positions": [],
            "cursor": "",
        }

        result = tracker.get_current_positions()

        assert result == []

    def test_pagination_single_page(self, tracker, mock_client):
        """Fetches positions from a single page."""
        mock_client.get_positions.return_value = {
            "market_positions": [{"ticker": "A", "position": 1}],
            "cursor": "",
        }

        result = tracker.get_current_positions()

        assert len(result) == 1
        mock_client.get_positions.assert_called_once_with(limit=100, cursor=None)

    def test_pagination_multiple_pages(self, tracker, mock_client):
        """Fetches positions across multiple pages."""
        mock_client.get_positions.side_effect = [
            {
                "market_positions": [{"ticker": "A", "position": 1}],
                "cursor": "page2",
            },
            {
                "market_positions": [{"ticker": "B", "position": 2}],
                "cursor": "",
            },
        ]

        result = tracker.get_current_positions()

        assert len(result) == 2
        assert mock_client.get_positions.call_count == 2
        mock_client.get_positions.assert_any_call(limit=100, cursor=None)
        mock_client.get_positions.assert_any_call(limit=100, cursor="page2")

    def test_handles_positions_key(self, tracker, mock_client):
        """Works with 'positions' key instead of 'market_positions'."""
        mock_client.get_positions.return_value = {
            "positions": [{"ticker": "A", "position": 3}],
            "cursor": "",
        }

        result = tracker.get_current_positions()

        assert len(result) == 1
        assert result[0]["ticker"] == "A"

    def test_api_error_raises_portfolio_error(self, tracker, mock_client):
        """Translates KalshiAPIError to PortfolioError."""
        mock_client.get_positions.side_effect = KalshiAPIError("Server error", status_code=500)

        with pytest.raises(PortfolioError) as exc_info:
            tracker.get_current_positions()

        assert "Failed to fetch positions" in str(exc_info.value)

    def test_all_zero_positions(self, tracker, mock_client):
        """Returns empty list when all positions are zero."""
        mock_client.get_positions.return_value = {
            "market_positions": [
                {"ticker": "A", "position": 0},
                {"ticker": "B", "position": 0},
            ],
            "cursor": "",
        }

        result = tracker.get_current_positions()

        assert result == []

    def test_missing_position_key_treated_as_zero(self, tracker, mock_client):
        """Position without 'position' key is treated as 0 and filtered out."""
        mock_client.get_positions.return_value = {
            "market_positions": [
                {"ticker": "A"},
                {"ticker": "B", "position": 5},
            ],
            "cursor": "",
        }

        result = tracker.get_current_positions()

        assert len(result) == 1
        assert result[0]["ticker"] == "B"


# =============================================================================
# Calculate Position P&L Tests
# =============================================================================

class TestCalculatePositionPnl:
    """Tests for calculate_position_pnl method."""

    def test_yes_position_profit(self, tracker, mock_client):
        """YES position with price increase shows profit."""
        mock_client.get_market.return_value = {
            "market": {
                "yes_bid": 70, "yes_ask": 74,
                "last_price": 72, "status": "active",
                "title": "Test Market", "result": "",
            }
        }

        pos = {"ticker": "TEST", "position": 5, "market_exposure": 250}
        result = tracker.calculate_position_pnl(pos)

        assert result["side"] == "yes"
        assert result["quantity"] == 5
        assert result["cost"] == 250
        # Midpoint = (70 + 74) // 2 = 72
        # Value = 5 * 72 = 360
        assert result["value"] == 360
        assert result["pnl"] == 110  # 360 - 250

    def test_yes_position_loss(self, tracker, mock_client):
        """YES position with price decrease shows loss."""
        mock_client.get_market.return_value = {
            "market": {
                "yes_bid": 30, "yes_ask": 34,
                "last_price": 32, "status": "active",
                "title": "Losing Market", "result": "",
            }
        }

        pos = {"ticker": "LOSE", "position": 10, "market_exposure": 600}
        result = tracker.calculate_position_pnl(pos)

        assert result["side"] == "yes"
        assert result["cost"] == 600
        # Midpoint = (30 + 34) // 2 = 32
        # Value = 10 * 32 = 320
        assert result["value"] == 320
        assert result["pnl"] == -280  # 320 - 600

    def test_no_position_profit(self, tracker, mock_client):
        """NO position (negative position) with price drop shows profit."""
        mock_client.get_market.return_value = {
            "market": {
                "yes_bid": 20, "yes_ask": 24,
                "last_price": 22, "status": "active",
                "title": "No Bet", "result": "",
            }
        }

        pos = {"ticker": "NOBET", "position": -3, "market_exposure": -120}
        result = tracker.calculate_position_pnl(pos)

        assert result["side"] == "no"
        assert result["quantity"] == 3
        assert result["cost"] == 120
        # Midpoint = (20 + 24) // 2 = 22
        # NO value = 3 * (100 - 22) = 3 * 78 = 234
        assert result["value"] == 234
        assert result["pnl"] == 114  # 234 - 120

    def test_no_position_loss(self, tracker, mock_client):
        """NO position with price increase shows loss."""
        mock_client.get_market.return_value = {
            "market": {
                "yes_bid": 80, "yes_ask": 84,
                "last_price": 82, "status": "active",
                "title": "No Loss", "result": "",
            }
        }

        pos = {"ticker": "NOLOSS", "position": -5, "market_exposure": -250}
        result = tracker.calculate_position_pnl(pos)

        assert result["side"] == "no"
        assert result["cost"] == 250
        # Midpoint = (80 + 84) // 2 = 82
        # NO value = 5 * (100 - 82) = 5 * 18 = 90
        assert result["value"] == 90
        assert result["pnl"] == -160  # 90 - 250

    def test_settled_yes_win(self, tracker, mock_client):
        """YES position on market that settled YES = full payout."""
        mock_client.get_market.return_value = {
            "market": {
                "yes_bid": 0, "yes_ask": 0,
                "last_price": 100, "status": "settled",
                "title": "Settled Yes", "result": "yes",
            }
        }

        pos = {"ticker": "SETTLED", "position": 4, "market_exposure": 200}
        result = tracker.calculate_position_pnl(pos)

        assert result["value"] == 400  # 4 * 100
        assert result["pnl"] == 200  # 400 - 200

    def test_settled_yes_lose(self, tracker, mock_client):
        """YES position on market that settled NO = zero payout."""
        mock_client.get_market.return_value = {
            "market": {
                "yes_bid": 0, "yes_ask": 0,
                "last_price": 0, "status": "settled",
                "title": "Settled No", "result": "no",
            }
        }

        pos = {"ticker": "LOST", "position": 4, "market_exposure": 200}
        result = tracker.calculate_position_pnl(pos)

        assert result["value"] == 0
        assert result["pnl"] == -200

    def test_settled_no_win(self, tracker, mock_client):
        """NO position on market that settled NO = full payout."""
        mock_client.get_market.return_value = {
            "market": {
                "yes_bid": 0, "yes_ask": 0,
                "last_price": 0, "status": "settled",
                "title": "No Wins", "result": "no",
            }
        }

        pos = {"ticker": "NOWIN", "position": -3, "market_exposure": -150}
        result = tracker.calculate_position_pnl(pos)

        assert result["side"] == "no"
        assert result["value"] == 300  # 3 * 100
        assert result["pnl"] == 150  # 300 - 150

    def test_settled_no_lose(self, tracker, mock_client):
        """NO position on market that settled YES = zero payout."""
        mock_client.get_market.return_value = {
            "market": {
                "yes_bid": 0, "yes_ask": 0,
                "last_price": 100, "status": "settled",
                "title": "No Loses", "result": "yes",
            }
        }

        pos = {"ticker": "NOLOSE", "position": -3, "market_exposure": -150}
        result = tracker.calculate_position_pnl(pos)

        assert result["value"] == 0
        assert result["pnl"] == -150

    def test_fallback_to_last_price(self, tracker, mock_client):
        """Uses last_price when bid/ask are zero."""
        mock_client.get_market.return_value = {
            "market": {
                "yes_bid": 0, "yes_ask": 0,
                "last_price": 55, "status": "active",
                "title": "Fallback", "result": "",
            }
        }

        pos = {"ticker": "FALL", "position": 2, "market_exposure": 80}
        result = tracker.calculate_position_pnl(pos)

        # Value = 2 * 55 = 110
        assert result["value"] == 110
        assert result["pnl"] == 30  # 110 - 80

    def test_fallback_to_zero_price(self, tracker, mock_client):
        """Uses zero when both bid/ask and last_price are zero."""
        mock_client.get_market.return_value = {
            "market": {
                "yes_bid": 0, "yes_ask": 0,
                "last_price": 0, "status": "active",
                "title": "No Price", "result": "",
            }
        }

        pos = {"ticker": "NOPRICE", "position": 2, "market_exposure": 80}
        result = tracker.calculate_position_pnl(pos)

        assert result["value"] == 0
        assert result["pnl"] == -80

    def test_api_error_raises_portfolio_error(self, tracker, mock_client):
        """Market lookup failure raises PortfolioError."""
        mock_client.get_market.side_effect = KalshiAPIError("Not found", status_code=404)

        pos = {"ticker": "GONE", "position": 1, "market_exposure": 50}

        with pytest.raises(PortfolioError) as exc_info:
            tracker.calculate_position_pnl(pos)

        assert "Failed to get market price" in str(exc_info.value)

    def test_market_response_without_wrapper(self, tracker, mock_client):
        """Handles API response without 'market' wrapper key."""
        mock_client.get_market.return_value = {
            "yes_bid": 60, "yes_ask": 64,
            "last_price": 62, "status": "active",
            "title": "No Wrapper", "result": "",
        }

        pos = {"ticker": "NOWRAP", "position": 1, "market_exposure": 50}
        result = tracker.calculate_position_pnl(pos)

        # Midpoint = (60 + 64) // 2 = 62
        assert result["value"] == 62
        assert result["pnl"] == 12


# =============================================================================
# Calculate Total P&L Tests
# =============================================================================

class TestCalculateTotalPnl:
    """Tests for calculate_total_pnl method."""

    def test_aggregates_multiple_positions(self, tracker, mock_client):
        """Sums P&L across multiple positions."""
        mock_client.get_positions.return_value = {
            "market_positions": [
                {"ticker": "A", "position": 5, "market_exposure": 250},
                {"ticker": "B", "position": 3, "market_exposure": 150},
            ],
            "cursor": "",
        }
        mock_client.get_market.side_effect = [
            {"market": {"yes_bid": 70, "yes_ask": 74, "last_price": 72,
                         "status": "active", "title": "A", "result": ""}},
            {"market": {"yes_bid": 40, "yes_ask": 44, "last_price": 42,
                         "status": "active", "title": "B", "result": ""}},
        ]

        result = tracker.calculate_total_pnl()

        # A: value = 5 * 72 = 360, cost = 250, pnl = 110
        # B: value = 3 * 42 = 126, cost = 150, pnl = -24
        assert result["total_cost"] == 400
        assert result["total_value"] == 486
        assert result["total_pnl"] == 86
        assert len(result["positions"]) == 2
        assert result["errors"] == []

    def test_empty_portfolio(self, tracker, mock_client):
        """Handles empty portfolio gracefully."""
        mock_client.get_positions.return_value = {
            "market_positions": [],
            "cursor": "",
        }

        result = tracker.calculate_total_pnl()

        assert result["total_cost"] == 0
        assert result["total_value"] == 0
        assert result["total_pnl"] == 0
        assert result["positions"] == []
        assert result["errors"] == []

    def test_skips_failed_positions(self, tracker, mock_client):
        """Skips positions that fail market lookup."""
        mock_client.get_positions.return_value = {
            "market_positions": [
                {"ticker": "GOOD", "position": 2, "market_exposure": 100},
                {"ticker": "BAD", "position": 3, "market_exposure": 150},
            ],
            "cursor": "",
        }
        mock_client.get_market.side_effect = [
            {"market": {"yes_bid": 60, "yes_ask": 64, "last_price": 62,
                         "status": "active", "title": "Good", "result": ""}},
            KalshiAPIError("Not found", status_code=404),
        ]

        result = tracker.calculate_total_pnl()

        # Only GOOD counted: value = 2 * 62 = 124, cost = 100, pnl = 24
        assert result["total_cost"] == 100
        assert result["total_pnl"] == 24
        assert len(result["positions"]) == 1
        assert result["errors"] == ["BAD"]

    def test_all_positions_fail(self, tracker, mock_client):
        """Returns zeros when all positions fail price lookup."""
        mock_client.get_positions.return_value = {
            "market_positions": [
                {"ticker": "BAD1", "position": 1, "market_exposure": 50},
                {"ticker": "BAD2", "position": 2, "market_exposure": 100},
            ],
            "cursor": "",
        }
        mock_client.get_market.side_effect = KalshiAPIError("Error", status_code=500)

        result = tracker.calculate_total_pnl()

        assert result["total_cost"] == 0
        assert result["total_value"] == 0
        assert result["total_pnl"] == 0
        assert result["positions"] == []
        assert result["errors"] == ["BAD1", "BAD2"]

    def test_fetch_error_propagates(self, tracker, mock_client):
        """PortfolioError from position fetch propagates up."""
        mock_client.get_positions.side_effect = KalshiAPIError("Down", status_code=500)

        with pytest.raises(PortfolioError):
            tracker.calculate_total_pnl()


# =============================================================================
# Get Realized P&L Tests
# =============================================================================

class TestGetRealizedPnl:
    """Tests for get_realized_pnl method (settlement-only scenarios)."""

    def _no_fills(self, mock_client):
        """Helper to mock empty fills response."""
        mock_client.get_fills.return_value = {"fills": [], "cursor": ""}

    def test_aggregates_realized_pnl(self, tracker, mock_client):
        """Sums realized P&L across settlements."""
        self._no_fills(mock_client)
        mock_client.get_settlements.return_value = {
            "settlements": [
                {"ticker": "A", "revenue": 500, "yes_total_cost": 275,
                 "no_total_cost": 0, "fee_cost": "0.2000", "market_result": "yes"},
                {"ticker": "B", "revenue": 0, "yes_total_cost": 200,
                 "no_total_cost": 0, "fee_cost": "0.1000", "market_result": "no"},
            ],
            "cursor": "",
        }

        result = tracker.get_realized_pnl()

        # A: pnl = 500 - 275 = 225, fees = 20
        # B: pnl = 0 - 200 = -200, fees = 10
        assert result["gross_pnl"] == 25
        assert result["total_fees"] == 30
        assert result["net_pnl"] == -5
        assert len(result["settlements"]) == 2

    def test_settlement_with_no_cost(self, tracker, mock_client):
        """Handles settlement with no cost (e.g. free position)."""
        self._no_fills(mock_client)
        mock_client.get_settlements.return_value = {
            "settlements": [
                {"ticker": "FREE", "revenue": 0, "yes_total_cost": 0,
                 "no_total_cost": 0, "fee_cost": "0.0000", "market_result": "no"},
            ],
            "cursor": "",
        }

        result = tracker.get_realized_pnl()

        assert len(result["settlements"]) == 1
        assert result["settlements"][0]["realized_pnl"] == 0
        assert result["net_pnl"] == 0

    def test_settlement_with_both_yes_and_no_cost(self, tracker, mock_client):
        """Handles settlement where both yes and no costs exist."""
        self._no_fills(mock_client)
        mock_client.get_settlements.return_value = {
            "settlements": [
                {"ticker": "BOTH", "revenue": 300, "yes_total_cost": 100,
                 "no_total_cost": 50, "fee_cost": "0.0500", "market_result": "yes"},
            ],
            "cursor": "",
        }

        result = tracker.get_realized_pnl()

        # pnl = 300 - 150 = 150, fees = 5
        assert result["settlements"][0]["realized_pnl"] == 150
        assert result["settlements"][0]["fees_paid"] == 5
        assert result["net_pnl"] == 145

    def test_empty_settlements(self, tracker, mock_client):
        """Handles no settlements and no fills."""
        self._no_fills(mock_client)
        mock_client.get_settlements.return_value = {
            "settlements": [],
            "cursor": "",
        }

        result = tracker.get_realized_pnl()

        assert result["gross_pnl"] == 0
        assert result["total_fees"] == 0
        assert result["net_pnl"] == 0
        assert result["settlements"] == []

    def test_api_error_raises_portfolio_error(self, tracker, mock_client):
        """Translates KalshiAPIError to PortfolioError."""
        mock_client.get_settlements.side_effect = KalshiAPIError("Error", status_code=500)

        with pytest.raises(PortfolioError) as exc_info:
            tracker.get_realized_pnl()

        assert "Failed to fetch settlements" in str(exc_info.value)

    def test_settlement_entries_have_source_key(self, tracker, mock_client):
        """Settlement entries include source='settlement'."""
        self._no_fills(mock_client)
        mock_client.get_settlements.return_value = {
            "settlements": [
                {"ticker": "A", "revenue": 100, "yes_total_cost": 50,
                 "no_total_cost": 0, "fee_cost": "0.0000", "market_result": "yes"},
            ],
            "cursor": "",
        }

        result = tracker.get_realized_pnl()

        assert result["settlements"][0]["source"] == "settlement"


# =============================================================================
# Display Portfolio Summary Tests
# =============================================================================

class TestDisplayPortfolioSummary:
    """Tests for display_portfolio_summary method."""

    def _no_fills(self, mock_client):
        """Helper to mock empty fills response."""
        mock_client.get_fills.return_value = {"fills": [], "cursor": ""}

    def test_displays_balance(self, tracker, mock_client, capsys):
        """Shows account balance in output."""
        self._no_fills(mock_client)
        mock_client.get_balance.return_value = {
            "balance": 25000, "portfolio_value": 4500,
        }
        mock_client.get_positions.return_value = {
            "market_positions": [], "cursor": "",
        }
        mock_client.get_settlements.return_value = {
            "settlements": [], "cursor": "",
        }

        tracker.display_portfolio_summary()

        output = capsys.readouterr().out
        assert "Portfolio Summary" in output
        assert "$250.00" in output
        assert "$45.00" in output
        assert "$295.00" in output

    def test_displays_no_open_positions(self, tracker, mock_client, capsys):
        """Shows 'No open positions' when portfolio is empty."""
        self._no_fills(mock_client)
        mock_client.get_balance.return_value = {
            "balance": 10000, "portfolio_value": 0,
        }
        mock_client.get_positions.return_value = {
            "market_positions": [], "cursor": "",
        }
        mock_client.get_settlements.return_value = {
            "settlements": [], "cursor": "",
        }

        tracker.display_portfolio_summary()

        output = capsys.readouterr().out
        assert "No open positions" in output

    def test_displays_position_details(self, tracker, mock_client, capsys):
        """Shows position ticker and P&L in output."""
        self._no_fills(mock_client)
        mock_client.get_balance.return_value = {
            "balance": 25000, "portfolio_value": 4500,
        }
        mock_client.get_positions.return_value = {
            "market_positions": [
                {"ticker": "KXBTC", "position": 5, "market_exposure": 250,
                 "realized_pnl": 0, "fees_paid": 0},
            ],
            "cursor": "",
        }
        mock_client.get_market.return_value = {
            "market": {
                "yes_bid": 60, "yes_ask": 64, "last_price": 62,
                "status": "active", "title": "Bitcoin Market", "result": "",
            }
        }
        mock_client.get_settlements.return_value = {
            "settlements": [], "cursor": "",
        }

        tracker.display_portfolio_summary()

        output = capsys.readouterr().out
        assert "KXBTC" in output
        assert "Bitcoin Market" in output

    def test_displays_realized_pnl(self, tracker, mock_client, capsys):
        """Shows realized P&L section."""
        self._no_fills(mock_client)
        mock_client.get_balance.return_value = {
            "balance": 25000, "portfolio_value": 0,
        }
        mock_client.get_positions.return_value = {
            "market_positions": [], "cursor": "",
        }
        mock_client.get_settlements.return_value = {
            "settlements": [
                {"ticker": "OLD", "revenue": 500, "yes_total_cost": 275,
                 "no_total_cost": 0, "fee_cost": "0.0900", "market_result": "yes"},
            ],
            "cursor": "",
        }

        tracker.display_portfolio_summary()

        output = capsys.readouterr().out
        assert "Realized P&L" in output
        assert "+$2.25" in output
        assert "$0.09" in output
        assert "+$2.16" in output

    def test_displays_fill_disclaimer(self, tracker, mock_client, capsys):
        """Shows NOTE disclaimer when fill-sourced P&L entries exist."""
        mock_client.get_balance.return_value = {
            "balance": 10000, "portfolio_value": 0,
        }
        mock_client.get_positions.return_value = {
            "market_positions": [], "cursor": "",
        }
        mock_client.get_settlements.return_value = {
            "settlements": [], "cursor": "",
        }
        mock_client.get_fills.return_value = {
            "fills": [
                {"ticker": "TRADED", "side": "yes", "action": "buy",
                 "count": 5, "yes_price": 40, "no_price": 60,
                 "fee_cost": "0.0000", "created_time": "2025-01-15T10:00:00Z"},
                {"ticker": "TRADED", "side": "yes", "action": "sell",
                 "count": 5, "yes_price": 60, "no_price": 40,
                 "fee_cost": "0.0000", "created_time": "2025-01-16T10:00:00Z"},
            ],
            "cursor": "",
        }

        tracker.display_portfolio_summary()

        output = capsys.readouterr().out
        assert "NOTE:" in output
        assert "estimated from fill data" in output


# =============================================================================
# Fetch All Fills Tests
# =============================================================================

class TestFetchAllFills:
    """Tests for _fetch_all_fills method."""

    def test_fetches_fills_single_page(self, tracker, mock_client):
        """Fetches fills from a single page."""
        mock_client.get_fills.return_value = {
            "fills": [{"fill_id": "f1"}, {"fill_id": "f2"}],
            "cursor": "",
        }

        result = tracker._fetch_all_fills()

        assert len(result) == 2
        mock_client.get_fills.assert_called_once_with(limit=100, cursor=None)

    def test_fetches_fills_multiple_pages(self, tracker, mock_client):
        """Paginates through multiple pages of fills."""
        mock_client.get_fills.side_effect = [
            {"fills": [{"fill_id": "f1"}], "cursor": "next"},
            {"fills": [{"fill_id": "f2"}], "cursor": ""},
        ]

        result = tracker._fetch_all_fills()

        assert len(result) == 2
        assert mock_client.get_fills.call_count == 2

    def test_api_error_raises_portfolio_error(self, tracker, mock_client):
        """Translates KalshiAPIError to PortfolioError."""
        mock_client.get_fills.side_effect = KalshiAPIError("Error", status_code=500)

        with pytest.raises(PortfolioError) as exc_info:
            tracker._fetch_all_fills()

        assert "Failed to fetch fills" in str(exc_info.value)


# =============================================================================
# Fetch All Settlements Tests
# =============================================================================

class TestFetchAllSettlements:
    """Tests for _fetch_all_settlements method."""

    def test_fetches_settlements_single_page(self, tracker, mock_client):
        """Fetches settlements from a single page."""
        mock_client.get_settlements.return_value = {
            "settlements": [{"ticker": "A"}, {"ticker": "B"}],
            "cursor": "",
        }

        result = tracker._fetch_all_settlements()

        assert len(result) == 2
        mock_client.get_settlements.assert_called_once_with(limit=100, cursor=None)

    def test_fetches_settlements_multiple_pages(self, tracker, mock_client):
        """Paginates through multiple pages of settlements."""
        mock_client.get_settlements.side_effect = [
            {"settlements": [{"ticker": "A"}], "cursor": "next"},
            {"settlements": [{"ticker": "B"}], "cursor": ""},
        ]

        result = tracker._fetch_all_settlements()

        assert len(result) == 2
        assert mock_client.get_settlements.call_count == 2

    def test_api_error_raises_portfolio_error(self, tracker, mock_client):
        """Translates KalshiAPIError to PortfolioError."""
        mock_client.get_settlements.side_effect = KalshiAPIError("Error", status_code=500)

        with pytest.raises(PortfolioError) as exc_info:
            tracker._fetch_all_settlements()

        assert "Failed to fetch settlements" in str(exc_info.value)


# =============================================================================
# Fill-Based Realized P&L Tests
# =============================================================================

class TestFillBasedRealizedPnl:
    """Tests for fill-based realized P&L calculation."""

    def _no_settlements(self, mock_client):
        """Helper to mock empty settlements response."""
        mock_client.get_settlements.return_value = {"settlements": [], "cursor": ""}

    def test_simple_yes_round_trip(self, tracker, mock_client):
        """Buy 5 YES at 40c, sell 5 YES at 60c = +100c profit."""
        self._no_settlements(mock_client)
        mock_client.get_fills.return_value = {
            "fills": [
                {"ticker": "TICKER-A", "side": "yes", "action": "buy",
                 "count": 5, "yes_price": 40, "no_price": 60,
                 "fee_cost": "0.0000", "created_time": "2025-01-15T10:00:00Z"},
                {"ticker": "TICKER-A", "side": "yes", "action": "sell",
                 "count": 5, "yes_price": 60, "no_price": 40,
                 "fee_cost": "0.0000", "created_time": "2025-01-16T10:00:00Z"},
            ],
            "cursor": "",
        }

        result = tracker.get_realized_pnl()

        assert result["gross_pnl"] == 100
        assert result["net_pnl"] == 100
        assert len(result["settlements"]) == 1
        assert result["settlements"][0]["source"] == "fills"
        assert result["settlements"][0]["realized_pnl"] == 100

    def test_simple_no_round_trip(self, tracker, mock_client):
        """Buy 3 NO (no_price=30), sell 3 NO (no_price=60) = +90c profit."""
        self._no_settlements(mock_client)
        mock_client.get_fills.return_value = {
            "fills": [
                {"ticker": "TICKER-B", "side": "no", "action": "buy",
                 "count": 3, "yes_price": 70, "no_price": 30,
                 "fee_cost": "0.0000", "created_time": "2025-01-15T10:00:00Z"},
                {"ticker": "TICKER-B", "side": "no", "action": "sell",
                 "count": 3, "yes_price": 40, "no_price": 60,
                 "fee_cost": "0.0000", "created_time": "2025-01-16T10:00:00Z"},
            ],
            "cursor": "",
        }

        result = tracker.get_realized_pnl()

        # (60 - 30) * 3 = 90
        assert result["gross_pnl"] == 90

    def test_partial_sell(self, tracker, mock_client):
        """Buy 10, sell 5 = only 5 contracts realized."""
        self._no_settlements(mock_client)
        mock_client.get_fills.return_value = {
            "fills": [
                {"ticker": "PART", "side": "yes", "action": "buy",
                 "count": 10, "yes_price": 40, "no_price": 60,
                 "fee_cost": "0.0000", "created_time": "2025-01-15T10:00:00Z"},
                {"ticker": "PART", "side": "yes", "action": "sell",
                 "count": 5, "yes_price": 60, "no_price": 40,
                 "fee_cost": "0.0000", "created_time": "2025-01-16T10:00:00Z"},
            ],
            "cursor": "",
        }

        result = tracker.get_realized_pnl()

        # Only 5 matched: (60 - 40) * 5 = 100
        assert result["gross_pnl"] == 100
        assert result["settlements"][0]["sell_count"] == 5

    def test_fill_based_loss(self, tracker, mock_client):
        """Buy at 60c, sell at 40c = loss."""
        self._no_settlements(mock_client)
        mock_client.get_fills.return_value = {
            "fills": [
                {"ticker": "LOSS", "side": "yes", "action": "buy",
                 "count": 5, "yes_price": 60, "no_price": 40,
                 "fee_cost": "0.0000", "created_time": "2025-01-15T10:00:00Z"},
                {"ticker": "LOSS", "side": "yes", "action": "sell",
                 "count": 5, "yes_price": 40, "no_price": 60,
                 "fee_cost": "0.0000", "created_time": "2025-01-16T10:00:00Z"},
            ],
            "cursor": "",
        }

        result = tracker.get_realized_pnl()

        # (40 - 60) * 5 = -100
        assert result["gross_pnl"] == -100

    def test_fifo_matching(self, tracker, mock_client):
        """FIFO: buy 3@30c, buy 3@50c, sell 4@60c = 90+10 = 100."""
        self._no_settlements(mock_client)
        mock_client.get_fills.return_value = {
            "fills": [
                {"ticker": "FIFO", "side": "yes", "action": "buy",
                 "count": 3, "yes_price": 30, "no_price": 70,
                 "fee_cost": "0.0000", "created_time": "2025-01-10T10:00:00Z"},
                {"ticker": "FIFO", "side": "yes", "action": "buy",
                 "count": 3, "yes_price": 50, "no_price": 50,
                 "fee_cost": "0.0000", "created_time": "2025-01-11T10:00:00Z"},
                {"ticker": "FIFO", "side": "yes", "action": "sell",
                 "count": 4, "yes_price": 60, "no_price": 40,
                 "fee_cost": "0.0000", "created_time": "2025-01-12T10:00:00Z"},
            ],
            "cursor": "",
        }

        result = tracker.get_realized_pnl()

        # FIFO: first 3 matched at 30c -> (60-30)*3=90
        #        next 1 matched at 50c -> (60-50)*1=10
        # total = 100
        assert result["gross_pnl"] == 100

    def test_sell_fees_included(self, tracker, mock_client):
        """Sell fees are deducted from net P&L."""
        self._no_settlements(mock_client)
        mock_client.get_fills.return_value = {
            "fills": [
                {"ticker": "FEES", "side": "yes", "action": "buy",
                 "count": 5, "yes_price": 40, "no_price": 60,
                 "fee_cost": "0.0000", "created_time": "2025-01-15T10:00:00Z"},
                {"ticker": "FEES", "side": "yes", "action": "sell",
                 "count": 5, "yes_price": 60, "no_price": 40,
                 "fee_cost": "0.2500", "created_time": "2025-01-16T10:00:00Z"},
            ],
            "cursor": "",
        }

        result = tracker.get_realized_pnl()

        assert result["gross_pnl"] == 100
        assert result["total_fees"] == 25
        assert result["net_pnl"] == 75

    def test_combined_fills_and_settlements_no_overlap(self, tracker, mock_client):
        """Fills for one ticker + settlement for another = both counted."""
        mock_client.get_settlements.return_value = {
            "settlements": [
                {"ticker": "SETTLED", "revenue": 500, "yes_total_cost": 300,
                 "no_total_cost": 0, "fee_cost": "0.1000", "market_result": "yes"},
            ],
            "cursor": "",
        }
        mock_client.get_fills.return_value = {
            "fills": [
                {"ticker": "TRADED", "side": "yes", "action": "buy",
                 "count": 5, "yes_price": 40, "no_price": 60,
                 "fee_cost": "0.0000", "created_time": "2025-01-15T10:00:00Z"},
                {"ticker": "TRADED", "side": "yes", "action": "sell",
                 "count": 5, "yes_price": 60, "no_price": 40,
                 "fee_cost": "0.0000", "created_time": "2025-01-16T10:00:00Z"},
            ],
            "cursor": "",
        }

        result = tracker.get_realized_pnl()

        # Settlement: 500 - 300 = 200, fees = 10
        # Fills: (60-40)*5 = 100, fees = 0
        assert result["gross_pnl"] == 300
        assert result["total_fees"] == 10
        assert result["net_pnl"] == 290
        assert len(result["settlements"]) == 2
        sources = {e["source"] for e in result["settlements"]}
        assert sources == {"settlement", "fills"}

    def test_overlapping_ticker_settlement_takes_precedence(self, tracker, mock_client):
        """When ticker has both settlement and fills, only settlement counted."""
        mock_client.get_settlements.return_value = {
            "settlements": [
                {"ticker": "OVERLAP", "revenue": 500, "yes_total_cost": 300,
                 "no_total_cost": 0, "fee_cost": "0.1000", "market_result": "yes"},
            ],
            "cursor": "",
        }
        mock_client.get_fills.return_value = {
            "fills": [
                {"ticker": "OVERLAP", "side": "yes", "action": "buy",
                 "count": 10, "yes_price": 30, "no_price": 70,
                 "fee_cost": "0.0000", "created_time": "2025-01-15T10:00:00Z"},
                {"ticker": "OVERLAP", "side": "yes", "action": "sell",
                 "count": 5, "yes_price": 60, "no_price": 40,
                 "fee_cost": "0.0000", "created_time": "2025-01-16T10:00:00Z"},
            ],
            "cursor": "",
        }

        result = tracker.get_realized_pnl()

        # Only settlement P&L counted: 500 - 300 = 200
        assert result["gross_pnl"] == 200
        assert len(result["settlements"]) == 1
        assert result["settlements"][0]["source"] == "settlement"

    def test_no_sell_fills_only_settlements(self, tracker, mock_client):
        """Buy fills only (no sells) = no fill-based P&L, only settlements."""
        mock_client.get_settlements.return_value = {
            "settlements": [
                {"ticker": "HELD", "revenue": 100, "yes_total_cost": 50,
                 "no_total_cost": 0, "fee_cost": "0.0000", "market_result": "yes"},
            ],
            "cursor": "",
        }
        mock_client.get_fills.return_value = {
            "fills": [
                {"ticker": "OPEN", "side": "yes", "action": "buy",
                 "count": 5, "yes_price": 40, "no_price": 60,
                 "fee_cost": "0.0000", "created_time": "2025-01-15T10:00:00Z"},
            ],
            "cursor": "",
        }

        result = tracker.get_realized_pnl()

        assert result["gross_pnl"] == 50
        assert len(result["settlements"]) == 1
        assert result["settlements"][0]["source"] == "settlement"

    def test_empty_fills_and_settlements(self, tracker, mock_client):
        """No fills and no settlements = all zeros."""
        mock_client.get_settlements.return_value = {"settlements": [], "cursor": ""}
        mock_client.get_fills.return_value = {"fills": [], "cursor": ""}

        result = tracker.get_realized_pnl()

        assert result["gross_pnl"] == 0
        assert result["total_fees"] == 0
        assert result["net_pnl"] == 0
        assert result["settlements"] == []

    def test_warning_for_ambiguous_tickers(self, tracker, mock_client, capsys):
        """Prints WARNING when ticker has both settlement and sell fills."""
        mock_client.get_settlements.return_value = {
            "settlements": [
                {"ticker": "MIXED", "revenue": 500, "yes_total_cost": 300,
                 "no_total_cost": 0, "fee_cost": "0.0000", "market_result": "yes"},
            ],
            "cursor": "",
        }
        mock_client.get_fills.return_value = {
            "fills": [
                {"ticker": "MIXED", "side": "yes", "action": "buy",
                 "count": 10, "yes_price": 30, "no_price": 70,
                 "fee_cost": "0.0000", "created_time": "2025-01-15T10:00:00Z"},
                {"ticker": "MIXED", "side": "yes", "action": "sell",
                 "count": 5, "yes_price": 60, "no_price": 40,
                 "fee_cost": "0.0000", "created_time": "2025-01-16T10:00:00Z"},
            ],
            "cursor": "",
        }

        tracker.get_realized_pnl()

        output = capsys.readouterr().out
        assert "WARNING" in output
        assert "MIXED" in output
        assert "may be incomplete" in output
