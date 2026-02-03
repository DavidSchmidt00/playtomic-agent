def create_booking_link(club_id: str, court_id: str, time: str, duration: int) -> str:
    """
    Creates a booking link for a specific slot.

    Args:
        club_id (str): The club ID.
        court_id (str): The court ID.
        time (str): The start time. (format: 2026-02-18T08:00:00.000Z)
        duration (int): The duration.

    Returns:
        str: The booking link.
    """
    return f"https://app.playtomic.com/payments?type=CUSTOMER_MATCH&tenant_id={club_id}&resource_id={court_id}&start={time.replace(':', '%3A')}&duration={duration}"
