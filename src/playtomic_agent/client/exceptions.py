"""Custom exceptions for Playtomic API client."""


class PlaytomicError(Exception):
    """Base exception for all Playtomic-related errors."""

    def __init__(self, message: str, details: dict | None = None):
        """Initialize PlaytomicError.

        Args:
            message: Error message
            details: Optional dictionary with additional error context
        """
        super().__init__(message)
        self.message = message
        self.details = details or {}

    def __str__(self) -> str:
        if self.details:
            details_str = ", ".join(f"{k}={v}" for k, v in self.details.items())
            return f"{self.message} ({details_str})"
        return self.message


class ClubNotFoundError(PlaytomicError):
    """Raised when a club cannot be found by slug or name."""

    def __init__(self, identifier: str, search_type: str = "slug"):
        """Initialize ClubNotFoundError.

        Args:
            identifier: The slug or name that was searched for
            search_type: Type of search performed ('slug' or 'name')
        """
        super().__init__(
            f"Club not found with {search_type}: {identifier}",
            details={"identifier": identifier, "search_type": search_type},
        )
        self.identifier = identifier
        self.search_type = search_type


class MultipleClubsFoundError(PlaytomicError):
    """Raised when multiple clubs are found for a single identifier."""

    def __init__(self, identifier: str, count: int):
        """Initialize MultipleClubsFoundError.

        Args:
            identifier: The identifier that was searched for
            count: Number of clubs found
        """
        super().__init__(
            f"Multiple clubs ({count}) found for identifier: {identifier}",
            details={"identifier": identifier, "count": count},
        )
        self.identifier = identifier
        self.count = count


class APIError(PlaytomicError):
    """Raised when the Playtomic API returns an error."""

    def __init__(
        self, message: str, status_code: int | None = None, response_data: dict | None = None
    ):
        """Initialize APIError.

        Args:
            message: Error message
            status_code: HTTP status code if available
            response_data: Response data from the API
        """
        details = {}
        if status_code:
            details["status_code"] = status_code
        if response_data:
            details["response"] = response_data

        super().__init__(message, details)
        self.status_code = status_code
        self.response_data = response_data


class ValidationError(PlaytomicError):
    """Raised when input validation fails."""

    def __init__(self, message: str, field: str | None = None):
        """Initialize ValidationError.

        Args:
            message: Error message
            field: Name of the field that failed validation
        """
        details = {"field": field} if field else {}
        super().__init__(message, details)
        self.field = field


class SlotNotFoundError(PlaytomicError):
    """Raised when no slots are found matching the criteria."""

    def __init__(self, club_slug: str, date: str, **filters):
        """Initialize SlotNotFoundError.

        Args:
            club_slug: Club identifier
            date: Date searched
            **filters: Additional filters applied
        """
        filters_str = ", ".join(f"{k}={v}" for k, v in filters.items() if v is not None)
        message = f"No slots found for {club_slug} on {date}"
        if filters_str:
            message += f" with filters: {filters_str}"

        super().__init__(message, details={"club_slug": club_slug, "date": date, **filters})
        self.club_slug = club_slug
        self.date = date
        self.filters = filters
