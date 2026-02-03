"""Tests for PlaytomicClient API client."""

from unittest.mock import Mock, patch

import pytest
import requests
from playtomic_agent.client.api import PlaytomicClient, find_slots
from playtomic_agent.client.exceptions import (
    APIError,
    ClubNotFoundError,
    MultipleClubsFoundError,
    ValidationError,
)


class TestPlaytomicClient:
    """Tests for PlaytomicClient class."""

    def test_client_initialization(self):
        """Test client initialization."""
        client = PlaytomicClient()
        assert client.api_base_url == "https://api.playtomic.io/v1"
        assert client.session is not None

    def test_client_custom_base_url(self):
        """Test client with custom base URL."""
        client = PlaytomicClient(api_base_url="https://custom.api.com/v1")
        assert client.api_base_url == "https://custom.api.com/v1"

    def test_client_context_manager(self):
        """Test client as context manager."""
        with PlaytomicClient() as client:
            assert client.session is not None
        # Session should be closed after exiting context

    @patch("playtomic_agent.client.api.requests.Session")
    def test_get_club_success(self, mock_session_class, mock_api_response_club):
        """Test successful club fetch."""
        # Setup mock
        mock_session = Mock()
        mock_session_class.return_value = mock_session
        mock_response = Mock()
        mock_response.json.return_value = mock_api_response_club
        mock_response.raise_for_status = Mock()
        mock_session.get.return_value = mock_response

        client = PlaytomicClient()
        club = client.get_club(slug="test-club")

        assert club.slug == "test-club"
        assert club.name == "Test Padel Club"
        assert len(club.courts) == 2

    @patch("playtomic_agent.client.api.requests.Session")
    def test_get_club_not_found(self, mock_session_class):
        """Test club not found."""
        # Setup mock for empty response
        mock_session = Mock()
        mock_session_class.return_value = mock_session
        mock_response = Mock()
        mock_response.json.return_value = []
        mock_response.raise_for_status = Mock()
        mock_session.get.return_value = mock_response

        client = PlaytomicClient()
        with pytest.raises(ClubNotFoundError):
            client.get_club(slug="nonexistent")

    @patch("playtomic_agent.client.api.requests.Session")
    def test_get_club_multiple_found(self, mock_session_class, mock_api_response_club):
        """Test multiple clubs found."""
        # Setup mock for multiple clubs
        mock_session = Mock()
        mock_session_class.return_value = mock_session
        mock_response = Mock()
        mock_response.json.return_value = [mock_api_response_club[0], mock_api_response_club[0]]
        mock_response.raise_for_status = Mock()
        mock_session.get.return_value = mock_response

        client = PlaytomicClient()
        with pytest.raises(MultipleClubsFoundError):
            client.get_club(slug="test-club")

    def test_get_club_no_identifier(self):
        """Test get club without slug or name."""
        client = PlaytomicClient()
        with pytest.raises(ValidationError):
            client.get_club()

    @patch("playtomic_agent.client.api.requests.Session")
    def test_get_club_api_error(self, mock_session_class):
        """Test API error during club fetch."""
        # Setup mock for API error
        mock_session = Mock()
        mock_session_class.return_value = mock_session
        mock_session.get.side_effect = requests.RequestException("Network error")

        client = PlaytomicClient()
        with pytest.raises(APIError):
            client.get_club(slug="test-club")

    @patch("playtomic_agent.client.api.requests.Session")
    def test_get_available_slots(self, mock_session_class, sample_club, mock_api_response_slots):
        """Test fetching available slots."""
        # Setup mock
        mock_session = Mock()
        mock_session_class.return_value = mock_session
        mock_response = Mock()
        mock_response.json.return_value = mock_api_response_slots
        mock_response.raise_for_status = Mock()
        mock_session.get.return_value = mock_response

        client = PlaytomicClient()
        slots = client.get_available_slots(sample_club, "2026-02-15")

        assert slots.club_id == sample_club.club_id
        assert slots.date == "2026-02-15"
        assert len(slots.slots) > 0

    def test_filter_slots_by_court_type(self, sample_club, sample_available_slots):
        """Test filtering slots by court type."""
        client = PlaytomicClient()

        # Filter for double courts
        double_slots = client.filter_slots(sample_club, sample_available_slots, court_type="DOUBLE")
        assert len(double_slots) == 2
        assert all(s.court_id in ["court-1", "court-3"] for s in double_slots)

        # Filter for single courts
        single_slots = client.filter_slots(sample_club, sample_available_slots, court_type="SINGLE")
        assert len(single_slots) == 1
        assert single_slots[0].court_id == "court-2"

    def test_filter_slots_by_duration(self, sample_club, sample_available_slots):
        """Test filtering slots by duration."""
        client = PlaytomicClient()

        # Filter for 90-minute slots
        slots_90 = client.filter_slots(sample_club, sample_available_slots, duration=90)
        assert len(slots_90) == 2
        assert all(s.duration == 90 for s in slots_90)

        # Filter for 60-minute slots
        slots_60 = client.filter_slots(sample_club, sample_available_slots, duration=60)
        assert len(slots_60) == 1
        assert slots_60[0].duration == 60

    def test_find_slots_no_timezone(self):
        """Test find_slots raises error when time filter without timezone."""
        client = PlaytomicClient()
        with pytest.raises(ValidationError, match="timezone is required"):
            client.find_slots(club_slug="test-club", date="2026-02-15", start_time="10:00")


class TestBackwardCompatibility:
    """Tests for backward-compatible find_slots function."""

    @patch("playtomic_agent.client.api.PlaytomicClient")
    def test_find_slots_returns_none_on_error(self, mock_client_class):
        """Test that backward-compatible function returns None on error."""
        # Setup mock to raise exception
        mock_client = Mock()
        mock_client.__enter__ = Mock(return_value=mock_client)
        mock_client.__exit__ = Mock(return_value=False)
        mock_client.find_slots.side_effect = APIError("Test error")
        mock_client_class.return_value = mock_client

        result = find_slots("test-club", "2026-02-15")
        assert result is None
