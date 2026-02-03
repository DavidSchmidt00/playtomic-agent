"""Tests for custom exceptions."""

from playtomic_agent.client.exceptions import (
    APIError,
    ClubNotFoundError,
    MultipleClubsFoundError,
    PlaytomicError,
    SlotNotFoundError,
    ValidationError,
)


class TestPlaytomicError:
    """Tests for base PlaytomicError."""

    def test_basic_error(self):
        """Test basic error creation."""
        error = PlaytomicError("Test error")
        assert str(error) == "Test error"
        assert error.message == "Test error"
        assert error.details == {}

    def test_error_with_details(self):
        """Test error with details."""
        error = PlaytomicError("Test error", details={"key": "value"})
        assert "key=value" in str(error)
        assert error.details == {"key": "value"}


class TestClubNotFoundError:
    """Tests for ClubNotFoundError."""

    def test_club_not_found_by_slug(self):
        """Test club not found error with slug."""
        error = ClubNotFoundError("test-club", "slug")
        assert "test-club" in str(error)
        assert "slug" in str(error)
        assert error.identifier == "test-club"
        assert error.search_type == "slug"

    def test_club_not_found_by_name(self):
        """Test club not found error with name."""
        error = ClubNotFoundError("Test Club", "name")
        assert "Test Club" in str(error)
        assert error.search_type == "name"


class TestMultipleClubsFoundError:
    """Tests for MultipleClubsFoundError."""

    def test_multiple_clubs_found(self):
        """Test multiple clubs error."""
        error = MultipleClubsFoundError("test", 3)
        assert "test" in str(error)
        assert "3" in str(error)
        assert error.count == 3


class TestAPIError:
    """Tests for APIError."""

    def test_api_error_basic(self):
        """Test basic API error."""
        error = APIError("API failed")
        assert str(error) == "API failed"
        assert error.status_code is None

    def test_api_error_with_status(self):
        """Test API error with status code."""
        error = APIError("Not found", status_code=404)
        assert error.status_code == 404
        assert "404" in str(error)

    def test_api_error_with_response(self):
        """Test API error with response data."""
        response = {"error": "Invalid request"}
        error = APIError("Bad request", status_code=400, response_data=response)
        assert error.response_data == response


class TestValidationError:
    """Tests for ValidationError."""

    def test_validation_error_basic(self):
        """Test basic validation error."""
        error = ValidationError("Invalid input")
        assert str(error) == "Invalid input"
        assert error.field is None

    def test_validation_error_with_field(self):
        """Test validation error with field."""
        error = ValidationError("Invalid value", field="timezone")
        assert "timezone" in str(error)
        assert error.field == "timezone"


class TestSlotNotFoundError:
    """Tests for SlotNotFoundError."""

    def test_slot_not_found_basic(self):
        """Test basic slot not found error."""
        error = SlotNotFoundError("test-club", "2026-02-15")
        assert "test-club" in str(error)
        assert "2026-02-15" in str(error)

    def test_slot_not_found_with_filters(self):
        """Test slot not found with filters."""
        error = SlotNotFoundError("test-club", "2026-02-15", court_type="DOUBLE", duration=90)
        assert "court_type=DOUBLE" in str(error)
        assert "duration=90" in str(error)
        assert error.filters["court_type"] == "DOUBLE"
