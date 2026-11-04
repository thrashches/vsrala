"""Pace helpers: convert speed (km/h) to min/km display."""

from __future__ import annotations

from decimal import Decimal
from typing import Optional, Union

Number = Union[int, float, Decimal]

# Speeds below this yield unreliable / infinite pace.
MIN_SPEED_KMH = 0.5


def speed_to_pace_seconds(speed_kmh: Optional[Number]) -> Optional[float]:
    """Return seconds per km for a given speed in km/h."""
    if speed_kmh is None:
        return None
    try:
        speed = float(speed_kmh)
    except (TypeError, ValueError):
        return None
    if speed < MIN_SPEED_KMH:
        return None
    return 3600.0 / speed


def format_pace(speed_kmh: Optional[Number]) -> Optional[str]:
    """Format speed (km/h) as pace string ``m:ss`` (without unit)."""
    seconds = speed_to_pace_seconds(speed_kmh)
    if seconds is None:
        return None
    total = max(0, int(round(seconds)))
    minutes, secs = divmod(total, 60)
    return f'{minutes}:{secs:02d}'


def format_pace_display(speed_kmh: Optional[Number]) -> Optional[str]:
    """Format speed as ``m:ss /км``."""
    pace = format_pace(speed_kmh)
    if pace is None:
        return None
    return f'{pace} /км'
