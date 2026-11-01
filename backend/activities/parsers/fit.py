from __future__ import annotations

import math
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import BinaryIO, Optional, Union

from fitparse import FitFile

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


def _semicircles_to_deg(value) -> Optional[float]:
    if value is None:
        return None
    return value * (180.0 / 2 ** 31)


def parse_fit(source: Union[str, Path, BinaryIO]) -> ParsedTrack:
    try:
        if hasattr(source, 'read'):
            if hasattr(source, 'seek'):
                source.seek(0)
            fit = FitFile(source)
        else:
            fit = FitFile(str(source))
    except Exception as exc:
        raise TrackParseError(f'Не удалось разобрать FIT: {exc}') from exc

    points = []
    times = []
    elevations = []
    hrs = []
    powers = []
    cadences = []
    speeds_raw = []

    try:
        records = list(fit.get_messages('record'))
    except Exception as exc:
        raise TrackParseError(f'Ошибка чтения FIT records: {exc}') from exc

    for record in records:
        data = {f.name: f.value for f in record}
        ts = data.get('timestamp')
        lat = _semicircles_to_deg(data.get('position_lat'))
        lon = _semicircles_to_deg(data.get('position_long'))
        if lat is not None and lon is not None and (abs(lat) > 90 or abs(lon) > 180):
            lat, lon = None, None

        hr = data.get('heart_rate')
        power = data.get('power')
        cad = data.get('cadence')
        elev = data.get('enhanced_altitude') or data.get('altitude')
        spd = data.get('enhanced_speed') or data.get('speed')
        dist = data.get('distance')

        # Keep records with GPS, or any useful indoor metrics / timestamp.
        has_gps = lat is not None and lon is not None
        has_metrics = any(v is not None for v in (hr, power, cad, elev, spd, dist, ts))
        if not has_gps and not has_metrics:
            continue

        points.append([lat, lon] if has_gps else None)
        times.append(ts)
        elevations.append(elev)
        hrs.append(int(hr) if hr is not None else None)
        powers.append(int(power) if power is not None else None)
        cadences.append(int(cad) if cad is not None else None)
        speeds_raw.append(spd * 3.6 if spd is not None else None)

    if not times and not any(p is not None for p in points):
        raise TrackParseError('FIT не содержит записей тренировки')

    total_distance = 0.0
    max_speed = 0.0
    moving_time = 0.0
    speeds = []

    for i in range(len(points)):
        speed = speeds_raw[i]
        if i > 0 and points[i] is not None and points[i - 1] is not None:
            d = _haversine_m(points[i - 1][0], points[i - 1][1], points[i][0], points[i][1])
            total_distance += d
            if times[i] and times[i - 1]:
                dt = (times[i] - times[i - 1]).total_seconds()
                if dt > 0:
                    if speed is None:
                        speed = (d / dt) * 3.6
                    if speed < 50:
                        moving_time += dt
        elif i > 0 and times[i] and times[i - 1] and speed is not None:
            dt = (times[i] - times[i - 1]).total_seconds()
            if dt > 0 and 0 < speed < 50:
                moving_time += dt
                total_distance += (speed / 3.6) * dt
        if speed is not None:
            if speed > max_speed and speed < 100:
                max_speed = speed
        speeds.append(round(speed, 2) if speed is not None else None)

    elev_gain, elev_loss, elev_min, elev_max = elevation_stats(elevations)

    session_distance = None
    session_moving = None
    session_avg_hr = None
    session_max_hr = None
    session_avg_power = None
    session_max_power = None
    session_avg_speed = None
    session_max_speed = None
    session_elev = None
    session_descent = None
    session_np = None
    session_tss = None
    session_avg_cadence = None
    session_max_cadence = None
    try:
        for session in fit.get_messages('session'):
            sdata = {f.name: f.value for f in session}
            if sdata.get('total_distance') is not None:
                session_distance = sdata['total_distance'] / 1000.0
            if sdata.get('total_timer_time') is not None:
                session_moving = sdata['total_timer_time']
            session_avg_hr = sdata.get('avg_heart_rate') or session_avg_hr
            session_max_hr = sdata.get('max_heart_rate') or session_max_hr
            session_avg_power = sdata.get('avg_power') or session_avg_power
            session_max_power = sdata.get('max_power') or session_max_power
            if sdata.get('enhanced_avg_speed') is not None:
                session_avg_speed = sdata['enhanced_avg_speed'] * 3.6
            elif sdata.get('avg_speed') is not None:
                session_avg_speed = sdata['avg_speed'] * 3.6
            if sdata.get('enhanced_max_speed') is not None:
                session_max_speed = sdata['enhanced_max_speed'] * 3.6
            elif sdata.get('max_speed') is not None:
                session_max_speed = sdata['max_speed'] * 3.6
            session_elev = sdata.get('total_ascent') if sdata.get('total_ascent') is not None else session_elev
            session_descent = (
                sdata.get('total_descent') if sdata.get('total_descent') is not None else session_descent
            )
            if sdata.get('normalized_power') is not None:
                session_np = int(sdata['normalized_power'])
            if sdata.get('training_stress_score') is not None:
                session_tss = round(float(sdata['training_stress_score']), 1)
            session_avg_cadence = sdata.get('avg_cadence') or session_avg_cadence
            session_max_cadence = sdata.get('max_cadence') or session_max_cadence
    except Exception:
        pass

    valid_times = [t for t in times if t is not None]
    if valid_times:
        started_at = valid_times[0]
        if isinstance(started_at, datetime) and started_at.tzinfo is None:
            started_at = started_at.replace(tzinfo=timezone.utc)
        total_seconds = (valid_times[-1] - valid_times[0]).total_seconds()
        if total_seconds < 0:
            total_seconds = 0
    else:
        started_at = datetime.now(timezone.utc)
        total_seconds = moving_time

    if session_moving is not None:
        duration_active = timedelta(seconds=session_moving)
        duration = timedelta(seconds=max(total_seconds, session_moving))
    else:
        duration = timedelta(seconds=max(total_seconds, 0))
        duration_active = timedelta(seconds=max(moving_time, 0)) if moving_time else duration

    distance_km = round(session_distance if session_distance is not None else total_distance / 1000, 2)

    avg_speed, avg_moving_speed = speed_averages(
        distance_km,
        duration.total_seconds(),
        duration_active.total_seconds(),
    )
    # Prefer session avg as moving average when present (FIT avg_speed is usually moving)
    if session_avg_speed is not None:
        avg_moving_speed = round(session_avg_speed, 2)

    if session_max_speed is not None:
        max_speed = session_max_speed

    hr_vals = [h for h in hrs if h is not None]
    power_vals = [p for p in powers if p is not None]

    avg_hr = int(session_avg_hr) if session_avg_hr else (int(sum(hr_vals) / len(hr_vals)) if hr_vals else None)
    max_hr = int(session_max_hr) if session_max_hr else (max(hr_vals) if hr_vals else None)
    avg_power = int(session_avg_power) if session_avg_power else (
        int(sum(power_vals) / len(power_vals)) if power_vals else None
    )
    max_power = int(session_max_power) if session_max_power else (max(power_vals) if power_vals else None)

    elev_gain = round(float(session_elev), 1) if session_elev is not None else elev_gain
    elev_loss = round(float(session_descent), 1) if session_descent is not None else elev_loss

    n = len(points)
    time_stream = elapsed_seconds(times, valid_times[0] if valid_times else None)

    np_val = session_np
    if np_val is None and power_vals:
        np_val = normalized_power_from_stream(powers, time_stream)

    avg_cadence, max_cadence = cadence_stats(cadences)
    if session_avg_cadence is not None:
        avg_cadence = int(session_avg_cadence)
    if session_max_cadence is not None:
        max_cadence = int(session_max_cadence)

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

    gps_points = []
    gps_times = []
    for i, pt in enumerate(points):
        if pt is not None:
            gps_points.append(pt)
            gps_times.append(time_stream[i] if i < len(time_stream) else None)
    map_points = map_points_with_time(gps_points, gps_times)

    return ParsedTrack(
        started_at=started_at,
        duration=duration,
        duration_active=duration_active,
        distance_km=distance_km,
        avg_speed=avg_speed,
        avg_moving_speed=avg_moving_speed,
        max_speed=round(max_speed, 2) if max_speed else None,
        avg_hr=avg_hr,
        max_hr=max_hr,
        avg_power=avg_power,
        max_power=max_power,
        normalized_power=np_val,
        tss=session_tss,
        avg_cadence=avg_cadence,
        max_cadence=max_cadence,
        elevation_gain=elev_gain,
        elevation_loss=elev_loss,
        elevation_min=elev_min,
        elevation_max=elev_max,
        points=map_points,
        streams=streams,
    )
