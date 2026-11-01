from __future__ import annotations

import math
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import BinaryIO, Optional, Union

import gpxpy

from .base import ParsedTrack, TrackParseError, elapsed_seconds, map_points_with_time
from .metrics import (
    cadence_stats,
    elevation_stats,
    normalized_power_from_stream,
    speed_averages,
)


def _haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def _extension_value(point, names: tuple) -> Optional[float]:
    """Read Garmin/GPX extension values (hr, cad, power, etc.)."""
    for ext in point.extensions:
        tag = getattr(ext, 'tag', '') or ''
        local = tag.split('}')[-1].lower() if tag else ''
        if local in names and ext.text:
            try:
                return float(ext.text)
            except ValueError:
                pass
        for child in list(ext):
            ctag = getattr(child, 'tag', '') or ''
            clocal = ctag.split('}')[-1].lower() if ctag else ''
            if clocal in names and child.text:
                try:
                    return float(child.text)
                except ValueError:
                    pass
    return None


def parse_gpx(source: Union[str, Path, BinaryIO]) -> ParsedTrack:
    try:
        if hasattr(source, 'read'):
            content = source.read()
            if isinstance(content, bytes):
                content = content.decode('utf-8')
            gpx = gpxpy.parse(content)
        else:
            with open(source, 'r', encoding='utf-8') as f:
                gpx = gpxpy.parse(f)
    except Exception as exc:
        raise TrackParseError(f'Не удалось разобрать GPX: {exc}') from exc

    points = []
    times = []
    elevations = []
    hrs = []
    powers = []
    cadences = []
    speeds = []

    for track in gpx.tracks:
        for segment in track.segments:
            for point in segment.points:
                if point.latitude is None or point.longitude is None:
                    continue
                points.append([point.latitude, point.longitude])
                times.append(point.time)
                elevations.append(point.elevation)
                hr = _extension_value(point, ('hr', 'heartrate', 'heart_rate'))
                power = _extension_value(point, ('power',))
                cad = _extension_value(point, ('cad', 'cadence'))
                hrs.append(int(hr) if hr is not None else None)
                powers.append(int(power) if power is not None else None)
                cadences.append(int(cad) if cad is not None else None)

    if not points:
        for wp in gpx.waypoints:
            if wp.latitude is not None and wp.longitude is not None:
                points.append([wp.latitude, wp.longitude])
                times.append(wp.time)
                elevations.append(wp.elevation)
                hrs.append(None)
                powers.append(None)
                cadences.append(None)

    if not points:
        raise TrackParseError('GPX не содержит точек трека')

    total_distance = 0.0
    max_speed = 0.0
    moving_time = 0.0

    for i in range(len(points)):
        speed = None
        if i > 0:
            d = _haversine_m(points[i - 1][0], points[i - 1][1], points[i][0], points[i][1])
            total_distance += d
            if times[i] and times[i - 1]:
                dt = (times[i] - times[i - 1]).total_seconds()
                if dt > 0:
                    speed = (d / dt) * 3.6
                    if speed < 50:
                        moving_time += dt
                    if speed > max_speed and speed < 100:
                        max_speed = speed
        speeds.append(round(speed, 2) if speed is not None else None)

    elev_gain, elev_loss, elev_min, elev_max = elevation_stats(elevations)

    valid_times = [t for t in times if t is not None]
    if valid_times:
        started_at = valid_times[0]
        if started_at.tzinfo is None:
            started_at = started_at.replace(tzinfo=timezone.utc)
        total_seconds = (valid_times[-1] - valid_times[0]).total_seconds()
        if total_seconds < 0:
            total_seconds = 0
    else:
        started_at = datetime.now(timezone.utc)
        total_seconds = moving_time

    duration = timedelta(seconds=max(total_seconds, 0))
    duration_active = timedelta(seconds=max(moving_time, 0)) if moving_time else duration

    distance_km = round(total_distance / 1000, 2)
    avg_speed, avg_moving_speed = speed_averages(
        distance_km,
        duration.total_seconds(),
        duration_active.total_seconds(),
    )

    hr_vals = [h for h in hrs if h is not None]
    power_vals = [p for p in powers if p is not None]

    n = len(points)
    time_stream = elapsed_seconds(times, valid_times[0] if valid_times else None)

    np_val = normalized_power_from_stream(powers, time_stream) if power_vals else None
    avg_cadence, max_cadence = cadence_stats(cadences)

    streams = {
        'time': time_stream,
        'speed': speeds,
        'hr': hrs if hr_vals else [],
        'power': powers if power_vals else [],
        'cadence': cadences if avg_cadence is not None else [],
        'ele': [
            round(elevations[i], 1) if elevations[i] is not None else None
            for i in range(n)
        ],
    }

    map_points = map_points_with_time(points, time_stream)

    return ParsedTrack(
        started_at=started_at,
        duration=duration,
        duration_active=duration_active,
        distance_km=distance_km,
        avg_speed=avg_speed,
        avg_moving_speed=avg_moving_speed,
        max_speed=round(max_speed, 2) if max_speed else None,
        avg_hr=int(sum(hr_vals) / len(hr_vals)) if hr_vals else None,
        max_hr=max(hr_vals) if hr_vals else None,
        avg_power=int(sum(power_vals) / len(power_vals)) if power_vals else None,
        max_power=max(power_vals) if power_vals else None,
        normalized_power=np_val,
        tss=None,
        avg_cadence=avg_cadence,
        max_cadence=max_cadence,
        elevation_gain=elev_gain,
        elevation_loss=elev_loss,
        elevation_min=elev_min,
        elevation_max=elev_max,
        points=map_points,
        streams=streams,
    )
