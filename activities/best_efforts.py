"""Best distance splits and peak power efforts for a single activity."""

from __future__ import annotations

import math
from typing import Any, Optional, Sequence

DISTANCE_TARGETS_KM = (1, 5, 10, 20, 25, 40, 50, 80, 100, 160, 200)

POWER_WINDOWS_SEC = (
    5,
    15,
    30,
    60,
    120,
    180,
    300,
    480,
    600,
    900,
    1200,
    1800,
    2700,
    3600,
)


def format_effort_duration(seconds: float) -> str:
    total = max(0, int(round(seconds)))
    if total < 60:
        return f'{total} с'
    minutes, secs = divmod(total, 60)
    if minutes < 60:
        return f'{minutes}:{secs:02d}'
    hours, minutes = divmod(minutes, 60)
    return f'{hours}:{minutes:02d}:{secs:02d}'


def format_power_window(seconds: int) -> str:
    if seconds < 60:
        return f'{seconds} с'
    minutes = seconds // 60
    return f'{minutes} мин'


def _haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def _cumulative_distance_from_speed(
    speeds: Sequence[Optional[float]],
    times: Sequence[Optional[float]],
) -> tuple[list[float], list[float]]:
    """Return (times_sec, cum_distance_km) parallel arrays."""
    if not speeds:
        return [], []
    n = len(speeds)
    out_t: list[float] = []
    out_d: list[float] = []
    cum = 0.0

    def t_at(i: int) -> float:
        if i < len(times) and times[i] is not None:
            return float(times[i])
        return float(i)

    for i in range(n):
        ti = t_at(i)
        if i == 0:
            out_t.append(ti)
            out_d.append(0.0)
            continue
        dt = max(0.0, ti - t_at(i - 1))
        spd = speeds[i - 1]
        if spd is None:
            spd = speeds[i]
        if spd is not None and dt > 0 and 0 < float(spd) < 100:
            cum += (float(spd) / 3.6) * dt / 1000.0
        out_t.append(ti)
        out_d.append(cum)
    return out_t, out_d


def _cumulative_distance_from_points(
    points: Sequence[Sequence[Any]],
) -> tuple[list[float], list[float]]:
    """Build (times_sec, cum_km) from track_points [[lat, lon, elapsed?], ...]."""
    if not points or len(points) < 2:
        return [], []
    out_t: list[float] = []
    out_d: list[float] = []
    cum = 0.0
    for i, pt in enumerate(points):
        if len(pt) < 2 or pt[0] is None or pt[1] is None:
            continue
        if len(pt) >= 3 and pt[2] is not None:
            t = float(pt[2])
        else:
            t = float(i)
        if not out_t:
            out_t.append(t)
            out_d.append(0.0)
            prev = pt
            continue
        d = _haversine_m(float(prev[0]), float(prev[1]), float(pt[0]), float(pt[1]))
        cum += d / 1000.0
        out_t.append(t)
        out_d.append(cum)
        prev = pt
    return out_t, out_d


def _best_time_for_distance(times: list[float], cum_km: list[float], target_km: float) -> Optional[float]:
    """Minimum elapsed seconds to cover target_km anywhere in the ride."""
    n = len(cum_km)
    if n < 2 or cum_km[-1] < target_km:
        return None
    best: Optional[float] = None
    j = 0
    for i in range(n):
        while j < n and cum_km[j] - cum_km[i] < target_km:
            j += 1
        if j >= n:
            break
        # Interpolate if we overshot
        dist = cum_km[j] - cum_km[i]
        if dist < target_km:
            continue
        if j > i and cum_km[j] > cum_km[i]:
            # fraction into segment j-1 → j from point where window starts at i
            # Actually window is from i to j; if overshoot, interpolate end time
            prev_dist = cum_km[j - 1] - cum_km[i] if j > i else 0.0
            if dist > target_km and j > i and (cum_km[j] - cum_km[j - 1]) > 0:
                need = target_km - prev_dist
                seg = cum_km[j] - cum_km[j - 1]
                frac = need / seg if seg > 0 else 1.0
                frac = max(0.0, min(1.0, frac))
                t_end = times[j - 1] + frac * (times[j] - times[j - 1])
            else:
                t_end = times[j]
            elapsed = t_end - times[i]
            if elapsed > 0 and (best is None or elapsed < best):
                best = elapsed
    return best


def best_distance_efforts(
    streams: dict,
    track_points: Optional[Sequence] = None,
    targets_km: Sequence[float] = DISTANCE_TARGETS_KM,
) -> list[dict[str, Any]]:
    speeds = streams.get('speed') or []
    times = streams.get('time') or []
    t_arr, d_arr = _cumulative_distance_from_speed(speeds, times)
    if len(d_arr) < 2 or d_arr[-1] <= 0:
        t_arr, d_arr = _cumulative_distance_from_points(track_points or [])
    if len(d_arr) < 2 or d_arr[-1] <= 0:
        return []

    total = d_arr[-1]
    rows: list[dict[str, Any]] = []
    for target in targets_km:
        if target > total + 1e-6:
            continue
        best = _best_time_for_distance(t_arr, d_arr, float(target))
        if best is None or best <= 0:
            continue
        speed_kmh = float(target) * 3600.0 / best
        speed_str = f'{speed_kmh:.1f}'.replace('.', ',')
        rows.append({
            'distance_km': target,
            'distance_display': f'{int(target) if target == int(target) else target} км',
            'seconds': best,
            'time_display': format_effort_duration(best),
            'speed_kmh': round(speed_kmh, 1),
            'speed_display': f'{speed_str} км/ч',
        })
    return rows


def _dense_power_series(
    powers: Sequence[Optional[int]],
    times: Sequence[Optional[float]],
) -> list[float]:
    """1 Hz forward-filled power series (same approach as NP helper)."""
    samples: list[tuple[float, float]] = []
    for i, p in enumerate(powers):
        if p is None:
            continue
        t = float(times[i]) if i < len(times) and times[i] is not None else float(i)
        samples.append((t, float(p)))
    if not samples:
        return []
    if len(samples) == 1:
        return [samples[0][1]]

    t0 = samples[0][0]
    t1 = samples[-1][0]
    if t1 <= t0:
        return [p for _, p in samples]

    duration = int(math.floor(t1 - t0)) + 1
    series = [0.0] * duration
    idx = 0
    for sec in range(duration):
        t = t0 + sec
        while idx + 1 < len(samples) and samples[idx + 1][0] <= t:
            idx += 1
        series[sec] = samples[idx][1]
    return series


def best_power_efforts(
    streams: dict,
    windows_sec: Sequence[int] = POWER_WINDOWS_SEC,
) -> list[dict[str, Any]]:
    powers = streams.get('power') or []
    times = streams.get('time') or []
    if not any(p is not None for p in powers):
        return []

    series = _dense_power_series(powers, times)
    if not series:
        return []

    n = len(series)
    # Prefix sums for O(1) window averages
    prefix = [0.0] * (n + 1)
    for i, v in enumerate(series):
        prefix[i + 1] = prefix[i] + v

    rows: list[dict[str, Any]] = []
    for window in windows_sec:
        if window > n:
            continue
        best = None
        for start in range(0, n - window + 1):
            avg = (prefix[start + window] - prefix[start]) / window
            if best is None or avg > best:
                best = avg
        if best is None:
            continue
        watts = int(round(best))
        rows.append({
            'window_sec': window,
            'window_display': format_power_window(window),
            'watts': watts,
            'watts_display': f'{watts} W',
        })
    return rows


def build_best_efforts(activity) -> dict[str, Any]:
    streams = activity.streams or {}
    distance_rows = best_distance_efforts(streams, activity.track_points or [])
    power_rows = best_power_efforts(streams)
    return {
        'distance_efforts': distance_rows,
        'power_efforts': power_rows,
        'has_distance_efforts': bool(distance_rows),
        'has_power_efforts': bool(power_rows),
    }
