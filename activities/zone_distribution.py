"""Time-in-zone distribution from activity streams."""

from __future__ import annotations

from typing import Any, Optional, Sequence

from profiles.zones import zone_index

# Soft lavender bars matching zone-analysis UI reference.
BAR_COLOR = '#C4B5FD'


def stream_has_data(values: Any) -> bool:
    if not values:
        return False
    return any(v is not None for v in values)


def format_duration(seconds: float) -> str:
    total = max(0, int(round(seconds)))
    if total < 60:
        return f'{total} с.'
    minutes, secs = divmod(total, 60)
    if minutes < 60:
        return f'{minutes}:{secs:02d}'
    hours, minutes = divmod(minutes, 60)
    return f'{hours}:{minutes:02d}:{secs:02d}'


def _format_range_for_display(zones: list[dict[str, Any]], index: int) -> str:
    """Format bounds: '525+' for open top zone, '420 - 525' otherwise."""
    zone = zones[index]
    lo = int(zone.get('min') or 0)
    hi = zone.get('max')
    n = len(zones)
    if index == n - 1 or hi is None:
        return f'{lo}+'
    return f'{lo} - {int(hi)}'


def compute_zone_distribution(
    values: Sequence[Optional[float]],
    times: Sequence[Optional[float]],
    zones: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Return rows for each zone (highest first: Z7…Z1)."""
    n_zones = len(zones)
    seconds = [0.0] * n_zones
    if not values or not zones:
        return _empty_rows(zones, seconds)

    length = len(values)
    times_list = list(times) if times else []

    def sample_time(i: int) -> float:
        if i < len(times_list) and times_list[i] is not None:
            return float(times_list[i])
        return float(i)

    for i in range(length):
        v = values[i]
        if v is None:
            continue
        idx = zone_index(v, zones)
        if idx is None:
            continue
        t0 = sample_time(i)
        if i + 1 < length:
            t1 = sample_time(i + 1)
            dt = max(0.0, t1 - t0)
        elif i > 0:
            dt = max(0.0, t0 - sample_time(i - 1))
        else:
            dt = 1.0
        if dt <= 0:
            dt = 1.0
        seconds[idx] += dt

    return _empty_rows(zones, seconds)


def _empty_rows(zones: list[dict[str, Any]], seconds: list[float]) -> list[dict[str, Any]]:
    total = sum(seconds)
    rows: list[dict[str, Any]] = []
    n = len(zones)
    for i in range(n - 1, -1, -1):
        sec = seconds[i] if i < len(seconds) else 0.0
        pct = (sec / total * 100.0) if total > 0 else 0.0
        pct_int = int(round(pct))
        rows.append({
            'zone_number': i + 1,
            'label': f'Z{i + 1}',
            'name': zones[i].get('name') or '',
            'range': _format_range_for_display(zones, i),
            'seconds': sec,
            'duration_display': format_duration(sec),
            'percent': pct_int,
            'percent_display': f'{pct_int}%',
            # String with a dot so Django L10N cannot turn it into "55,6" in CSS width.
            'bar_percent': f'{pct:.1f}',
            'color': BAR_COLOR,
            'has_time': sec > 0,
        })
    return rows
