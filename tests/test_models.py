"""Tests for Pydantic models."""

from datetime import datetime
from zoneinfo import ZoneInfo

from playtomic_agent.models import Court, Slot


class TestCourt:
    """Tests for Court model."""

    def test_court_creation(self):
        """Test creating a court."""
        court = Court(id="court-1", name="Court 1", type="double")
        assert court.id == "court-1"
        assert court.name == "Court 1"
        assert court.type == "double"

    def test_court_type_normalization(self):
        """Test that court type is normalized to lowercase."""
        court = Court(id="court-1", name="Court 1", type="DOUBLE")
        assert court.type == "double"

    def test_court_str(self):
        """Test court string representation."""
        court = Court(id="court-1", name="Court 1", type="double")
        assert str(court) == "Court 1 (court-1)"


class TestClub:
    """Tests for Club model."""

    def test_club_creation(self, sample_club):
        """Test creating a club."""
        assert sample_club.slug == "test-club"
        assert sample_club.name == "Test Padel Club"
        assert len(sample_club.courts) == 3

    def test_get_court_by_id(self, sample_club):
        """Test getting court by ID."""
        court = sample_club.get_court_by_id("court-1")
        assert court is not None
        assert court.name == "Court 1"

    def test_get_court_by_id_not_found(self, sample_club):
        """Test getting non-existent court by ID."""
        court = sample_club.get_court_by_id("nonexistent")
        assert court is None

    def test_get_court_by_type(self, sample_club):
        """Test getting courts by type."""
        double_courts = sample_club.get_court_by_type("double")
        assert len(double_courts) == 2
        assert all(c.type == "double" for c in double_courts)

        single_courts = sample_club.get_court_by_type("single")
        assert len(single_courts) == 1
        assert single_courts[0].type == "single"


class TestSlot:
    """Tests for Slot model."""

    def test_slot_creation(self):
        """Test creating a slot."""
        slot = Slot(
            club_id="club-123",
            court_id="court-1",
            court_name="Court 1",
            time=datetime(2026, 2, 15, 10, 0, 0, tzinfo=ZoneInfo("UTC")),
            duration=90,
            price="25.00 EUR",
        )
        assert slot.duration == 90
        assert slot.price == "25.00 EUR"

    def test_slot_to_json(self):
        """Test slot JSON serialization."""
        slot = Slot(
            club_id="club-123",
            court_id="court-1",
            court_name="Court 1",
            time=datetime(2026, 2, 15, 10, 0, 0, tzinfo=ZoneInfo("UTC")),
            duration=90,
            price="25.00 EUR",
        )
        json_data = slot.to_json()
        assert json_data["club_id"] == "club-123"
        assert json_data["court_id"] == "court-1"
        assert json_data["duration"] == 90
        assert "2026-02-15" in json_data["time"]

    def test_slot_get_link(self):
        """Test generating booking link."""
        slot = Slot(
            club_id="club-123",
            court_id="court-1",
            court_name="Court 1",
            time=datetime(2026, 2, 15, 10, 0, 0, tzinfo=ZoneInfo("UTC")),
            duration=90,
            price="25.00 EUR",
        )
        link = slot.get_link()
        assert "playtomic.com" in link
        assert "club-123" in link
        assert "court-1" in link
        assert "duration=90" in link
