"""Pytest configuration and fixtures for tests."""

from datetime import datetime
from unittest.mock import Mock, patch
from zoneinfo import ZoneInfo

import pytest
from playtomic_agent.models import Club, Court, Slot


@pytest.fixture(autouse=True)
def mock_settings():
    """Mock settings to avoid requiring .env file in tests."""
    mock_settings_obj = Mock()
    mock_settings_obj.gemini_api_key_free = "test-key-free"
    mock_settings_obj.gemini_api_key_paid = "test-key-paid"
    mock_settings_obj.default_timezone = "Europe/Berlin"
    mock_settings_obj.default_model = "gemini-3-flash-preview"
    mock_settings_obj.playtomic_api_base_url = "https://api.playtomic.io/v1"
    mock_settings_obj.rate_limit_free = 15
    mock_settings_obj.rate_limit_paid = 1000
    mock_settings_obj.rate_limit_pro = 2000
    mock_settings_obj.log_level = "INFO"

    with patch("playtomic_agent.client.api.get_settings", return_value=mock_settings_obj):
        yield mock_settings_obj


@pytest.fixture
def sample_club():
    """Create a sample club for testing."""
    return Club(
        slug="test-club",
        name="Test Padel Club",
        club_id="test-club-123",
        timezone="Europe/Berlin",
        courts=[
            Court(id="court-1", name="Court 1", type="double"),
            Court(id="court-2", name="Court 2", type="single"),
            Court(id="court-3", name="Court 3", type="double"),
        ],
    )


@pytest.fixture
def sample_slots(sample_club):
    """Create sample slots for testing."""
    base_time = datetime(2026, 2, 15, 10, 0, 0, tzinfo=ZoneInfo("UTC"))

    return [
        Slot(
            club_id=sample_club.club_id,
            court_id="court-1",
            court_name="Court 1",
            time=base_time,
            duration=90,
            price="25.00 EUR",
        ),
        Slot(
            club_id=sample_club.club_id,
            court_id="court-2",
            court_name="Court 2",
            time=base_time,
            duration=60,
            price="18.00 EUR",
        ),
        Slot(
            club_id=sample_club.club_id,
            court_id="court-3",
            court_name="Court 3",
            time=base_time.replace(hour=14),
            duration=90,
            price="25.00 EUR",
        ),
    ]


@pytest.fixture
def mock_api_response_club():
    """Mock API response for club data."""
    return [
        {
            "tenant_uid": "test-club",
            "tenant_name": "Test Padel Club",
            "tenant_id": "test-club-123",
            "address": {"timezone": "Europe/Berlin"},
            "resources": [
                {
                    "resource_id": "court-1",
                    "name": "Court 1",
                    "properties": {"resource_size": "double"},
                },
                {
                    "resource_id": "court-2",
                    "name": "Court 2",
                    "properties": {"resource_size": "single"},
                },
            ],
        }
    ]


@pytest.fixture
def mock_api_response_slots():
    """Mock API response for availability data."""
    return [
        {
            "resource_id": "court-1",
            "slots": [
                {"start_time": "10:00:00", "duration": 90, "price": "25.00 EUR"},
                {"start_time": "14:00:00", "duration": 90, "price": "25.00 EUR"},
            ],
        },
        {
            "resource_id": "court-2",
            "slots": [{"start_time": "10:00:00", "duration": 60, "price": "18.00 EUR"}],
        },
    ]
