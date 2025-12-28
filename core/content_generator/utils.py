from __future__ import annotations

from datetime import timedelta

from django.utils import timezone


def get_exa_date_range_iso_strings(*, months_back: int) -> tuple[str, str]:
    """
    Exa expects date filters as strings (YYYY-MM-DD).
    """
    current_datetime = timezone.now()
    end_date_iso_format = current_datetime.date().isoformat()
    start_date_iso_format = (current_datetime - timedelta(days=months_back * 30)).date().isoformat()
    return start_date_iso_format, end_date_iso_format
