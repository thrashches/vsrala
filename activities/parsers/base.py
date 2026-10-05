from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import BinaryIO, Optional, Union


@dataclass
class ParsedTrack:
    started_at: datetime
    duration: timedelta
    duration_active: timedelta
    distance_km: float
    avg_speed: Optional[float] = None
    avg_moving_speed: Optional[float] = None
    max_speed: Optional[float] = None
    avg_hr: Optional[int] = None
    max_hr: Optional[int] = None
    avg_power: Optional[int] = None
    max_power: Optional[int] = None
    normalized_power: Optional[int] = None
    tss: Optional[float] = None
    avg_cadence: Optional[int] = None
    max_cadence: Optional[int] = None
    elevation_gain: Optional[float] = None
    elevation_loss: Optional[float] = None
    elevation_min: Optional[float] = None
    elevation_max: Optional[float] = None
    points: list = field(default_factory=list)  # [[lat, lon, elapsed_sec?], ...]
    streams: dict = field(default_factory=dict)  # speed, hr, power, ele, cadence, time


class TrackParseError(Exception):
    pass


def elapsed_seconds(times: list, started_at: Optional[datetime] = None) -> list:
    """Convert absolute timestamps to elapsed seconds from the first valid time."""
    t0 = started_at
    if t0 is None:
        for t in times:
            if t is not None:
                t0 = t
                break
    if t0 is None:
        return [float(i) for i in range(len(times))]

    result: list = []
    last = 0.0
    for i, t in enumerate(times):
        if t is not None:
            last = max(0.0, (t - t0).total_seconds())
            result.append(round(last, 1))
        elif result:
            result.append(round(last, 1))
        else:
            result.append(0.0)
    # Forward-fill already done; back-fill leading gaps if any were 0 while later exist
    return result


def map_points_with_time(points: list, times_sec: list, max_points: int = 2000) -> list:
    """Downsample track points for the map, keeping [lat, lon, elapsed_sec]."""
    n = len(points)
    if n == 0:
        return []
    step = max(1, n // max_points)
    out = []
    for i in range(0, n, step):
        t = times_sec[i] if i < len(times_sec) else None
        out.append([points[i][0], points[i][1], t])
    if out[-1][0] != points[-1][0] or out[-1][1] != points[-1][1]:
        t = times_sec[-1] if times_sec else None
        out.append([points[-1][0], points[-1][1], t])
    return out


def parse_track(source: Union[str, Path, BinaryIO], filename: Optional[str] = None) -> ParsedTrack:
    """Parse a GPX or FIT track file into a ParsedTrack."""
    from .fit import parse_fit
    from .gpx import parse_gpx

    name = filename or ''
    if hasattr(source, 'name') and not name:
        name = getattr(source, 'name', '') or ''
    if isinstance(source, (str, Path)):
        name = name or str(source)

    ext = Path(name).suffix.lower()
    if ext == '.gpx':
        return parse_gpx(source)
    if ext == '.fit':
        return parse_fit(source)
    raise TrackParseError(f'Неподдерживаемый формат файла: {ext or "unknown"}. Ожидается .gpx или .fit')
