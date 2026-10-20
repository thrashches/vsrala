"""Velodrome track analysis from activity streams (speed / distance / power)."""

from __future__ import annotations

import math
from decimal import Decimal
from typing import Any, Optional, Sequence

# Line labels used in UI / summaries.
LINE_SLOW = 'slow'
LINE_CORRIDOR = 'corridor'
LINE_STAYER = 'stayer'
LINE_BOARD = 'board'

LINE_LABELS_RU = {
    LINE_SLOW: 'Лазурка',
    LINE_CORRIDOR: 'Спринтерский коридор',
    LINE_STAYER: 'Стаерская',
    LINE_BOARD: 'Борт',
}

# Colours match real track markings (inline CSS — not Tailwind-dependent).
LINE_COLORS = {
    LINE_SLOW: '#38bdf8',      # azure / лазурка
    LINE_CORRIDOR: '#dc2626',  # red
    LINE_STAYER: '#2563eb',    # blue
    LINE_BOARD: '#ffffff',     # white
}

LINE_ORDER = (LINE_SLOW, LINE_CORRIDOR, LINE_STAYER, LINE_BOARD)

# Soft speed floor (km/h) — below this treat as slow / not racing on the banking.
SLOW_SPEED_KMH = 22.0
# Minimum moving speed to keep a sample in segmentation.
MOVING_SPEED_KMH = 8.0

# Effective lap length buckets relative to nominal measurement-line length L.
# L_eff / L:
#   < SHORT → inside / slow band (or incomplete)
#   ~1.0 → corridor
#   above STAYER → stayer
#   above BOARD → board
L_EFF_SHORT_RATIO = 0.96
L_EFF_CORRIDOR_MAX = 1.035
L_EFF_STAYER_MAX = 1.09

# Peak-to-peak speed amplitude (km/h) soft prior for height on banking.
AMP_CORRIDOR_MAX = 3.5
AMP_STAYER_MAX = 7.0

# Lap length must be within this band of L to count as a valid lap.
LAP_LENGTH_MIN_RATIO = 0.85
LAP_LENGTH_MAX_RATIO = 1.25

# Leader / draft detection.
MIN_POWER_SAMPLES = 30
DRAFT_PROXY_HIGH_RATIO = 1.05  # above session mean → pulling
DRAFT_PROXY_LOW_RATIO = 0.95   # below session mean → drafting
MIN_GROUP_SPEED_CV = 0.12      # speed must be fairly stable for pack riding


def _as_float_list(values: Sequence) -> list[Optional[float]]:
    out: list[Optional[float]] = []
    for v in values or []:
        if v is None:
            out.append(None)
            continue
        try:
            out.append(float(v))
        except (TypeError, ValueError):
            out.append(None)
    return out


def _stream_has_values(values: Sequence) -> bool:
    return any(v is not None for v in (values or []))


def _moving_average(values: list[Optional[float]], window: int) -> list[Optional[float]]:
    if window <= 1:
        return list(values)
    half = window // 2
    n = len(values)
    out: list[Optional[float]] = [None] * n
    for i in range(n):
        lo = max(0, i - half)
        hi = min(n, i + half + 1)
        chunk = [values[j] for j in range(lo, hi) if values[j] is not None]
        if chunk:
            out[i] = sum(chunk) / len(chunk)
    return out


def _build_distance_m(
    times: list[Optional[float]],
    speeds_kmh: list[Optional[float]],
    distances: list[Optional[float]],
) -> list[float]:
    """Return cumulative distance in metres, length == len(times)."""
    n = len(times)
    if n == 0:
        return []

    if distances and len(distances) == n and _stream_has_values(distances):
        # Prefer device distance; forward-fill and rebase to start at 0.
        filled: list[Optional[float]] = []
        last = None
        for d in distances:
            if d is not None:
                last = d
            filled.append(last)
        # Back-fill leading Nones.
        first = next((d for d in filled if d is not None), None)
        if first is None:
            return _integrate_speed_distance(times, speeds_kmh)
        base = first
        out = []
        for d in filled:
            if d is None:
                out.append(0.0)
            else:
                out.append(max(0.0, d - base))
        # Ensure monotonic non-decreasing.
        for i in range(1, n):
            if out[i] < out[i - 1]:
                out[i] = out[i - 1]
        return out

    return _integrate_speed_distance(times, speeds_kmh)


def _integrate_speed_distance(
    times: list[Optional[float]],
    speeds_kmh: list[Optional[float]],
) -> list[float]:
    n = len(times)
    out = [0.0] * n
    for i in range(1, n):
        t0, t1 = times[i - 1], times[i]
        v = speeds_kmh[i] if speeds_kmh[i] is not None else speeds_kmh[i - 1]
        if t0 is None or t1 is None or v is None:
            out[i] = out[i - 1]
            continue
        dt = t1 - t0
        if dt <= 0 or dt > 30:
            out[i] = out[i - 1]
            continue
        out[i] = out[i - 1] + (v / 3.6) * dt
    return out


def _mean(values: Sequence[float]) -> Optional[float]:
    if not values:
        return None
    return sum(values) / len(values)


def _cv(values: Sequence[float]) -> float:
    m = _mean(values)
    if m is None or m <= 0 or len(values) < 2:
        return 0.0
    var = sum((x - m) ** 2 for x in values) / len(values)
    return math.sqrt(var) / m


def _peak_to_peak(values: Sequence[float]) -> float:
    if not values:
        return 0.0
    return max(values) - min(values)


def _slice_valid(values: Sequence[Optional[float]], start: int, end: int) -> list[float]:
    return [v for v in values[start:end] if v is not None]


def segment_laps(
    times: list[Optional[float]],
    speeds_kmh: list[Optional[float]],
    dist_m: list[float],
    lap_length_m: float,
) -> list[dict[str, Any]]:
    """Cut stream into laps near nominal lap_length_m with phase on speed minima."""
    n = len(times)
    if n < 5 or lap_length_m <= 0:
        return []

    smoothed = _moving_average(speeds_kmh, window=5)

    # Find candidate start indices: local minima of smoothed speed while moving.
    minima: list[int] = []
    for i in range(2, n - 2):
        v = smoothed[i]
        if v is None or v < MOVING_SPEED_KMH:
            continue
        prev = smoothed[i - 1]
        nxt = smoothed[i + 1]
        if prev is None or nxt is None:
            continue
        if v <= prev and v <= nxt:
            minima.append(i)

    if not minima:
        # Fallback: cut every lap_length_m from cumulative distance.
        return _segment_by_distance_only(times, speeds_kmh, dist_m, lap_length_m)

    laps: list[dict[str, Any]] = []
    i = 0
    while i < len(minima) - 1:
        start = minima[i]
        # Pick the next minimum whose distance delta is closest to lap_length_m
        # within allowed ratio band.
        best_j = None
        best_err = None
        for j in range(i + 1, min(i + 8, len(minima))):
            d = dist_m[minima[j]] - dist_m[start]
            ratio = d / lap_length_m
            if ratio < LAP_LENGTH_MIN_RATIO or ratio > LAP_LENGTH_MAX_RATIO:
                continue
            err = abs(d - lap_length_m)
            if best_err is None or err < best_err:
                best_err = err
                best_j = j
        if best_j is None:
            i += 1
            continue
        end = minima[best_j]
        if end <= start + 2:
            i += 1
            continue
        lap = _lap_features(times, speeds_kmh, dist_m, start, end)
        if lap is not None:
            laps.append(lap)
        i = best_j

    if len(laps) < 2:
        fallback = _segment_by_distance_only(times, speeds_kmh, dist_m, lap_length_m)
        if len(fallback) > len(laps):
            return fallback
    return laps


def _segment_by_distance_only(
    times: list[Optional[float]],
    speeds_kmh: list[Optional[float]],
    dist_m: list[float],
    lap_length_m: float,
) -> list[dict[str, Any]]:
    n = len(times)
    if n < 5 or dist_m[-1] < lap_length_m * 0.9:
        return []
    laps: list[dict[str, Any]] = []
    start = 0
    # Skip leading stationary samples.
    while start < n and (speeds_kmh[start] is None or speeds_kmh[start] < MOVING_SPEED_KMH):
        start += 1
    target = dist_m[start] + lap_length_m
    i = start + 1
    while i < n:
        if dist_m[i] >= target:
            lap = _lap_features(times, speeds_kmh, dist_m, start, i)
            if lap is not None:
                laps.append(lap)
            start = i
            target = dist_m[start] + lap_length_m
        i += 1
    return laps


def _lap_features(
    times: list[Optional[float]],
    speeds_kmh: list[Optional[float]],
    dist_m: list[float],
    start: int,
    end: int,
) -> Optional[dict[str, Any]]:
    speed_vals = _slice_valid(speeds_kmh, start, end + 1)
    if len(speed_vals) < 3:
        return None
    l_eff = dist_m[end] - dist_m[start]
    if l_eff <= 0:
        return None
    t0 = times[start]
    t1 = times[end]
    if t0 is None or t1 is None or t1 <= t0:
        return None
    v_mean = _mean(speed_vals) or 0.0
    amp = _peak_to_peak(speed_vals)
    return {
        'start_idx': start,
        'end_idx': end,
        't_start': float(t0),
        't_end': float(t1),
        'duration_s': float(t1 - t0),
        'l_eff': round(l_eff, 2),
        'v_mean': round(v_mean, 2),
        'amp': round(amp, 2),
        'speed_cv': round(_cv(speed_vals), 4),
    }


def classify_line(lap: dict[str, Any], lap_length_m: float) -> tuple[str, float]:
    """Return (line_label, confidence 0..1)."""
    l_eff = float(lap['l_eff'])
    v_mean = float(lap['v_mean'])
    amp = float(lap['amp'])
    ratio = l_eff / lap_length_m if lap_length_m > 0 else 1.0

    if v_mean < SLOW_SPEED_KMH or ratio < L_EFF_SHORT_RATIO:
        # Low speed dominates even if length is noisy.
        conf = 0.55
        if v_mean < SLOW_SPEED_KMH - 4:
            conf = 0.8
        if ratio < L_EFF_SHORT_RATIO:
            conf = min(0.95, conf + 0.15)
        return LINE_SLOW, conf

    # Length bucket.
    if ratio <= L_EFF_CORRIDOR_MAX:
        length_line = LINE_CORRIDOR
    elif ratio <= L_EFF_STAYER_MAX:
        length_line = LINE_STAYER
    else:
        length_line = LINE_BOARD

    # Amplitude soft vote.
    if amp <= AMP_CORRIDOR_MAX:
        amp_line = LINE_CORRIDOR
    elif amp <= AMP_STAYER_MAX:
        amp_line = LINE_STAYER
    else:
        amp_line = LINE_BOARD

    if length_line == amp_line:
        return length_line, 0.85

    # Conflict: prefer length; amp slightly adjusts confidence / neighbour.
    # If length says corridor but amp is high, bump toward stayer only when
    # ratio already near stayer boundary.
    if length_line == LINE_CORRIDOR and amp_line != LINE_CORRIDOR:
        if ratio > 1.02:
            return LINE_STAYER, 0.55
        return LINE_CORRIDOR, 0.6
    if length_line == LINE_STAYER and amp_line == LINE_BOARD and ratio > 1.07:
        return LINE_BOARD, 0.55
    if length_line == LINE_BOARD and amp_line == LINE_CORRIDOR:
        return LINE_BOARD, 0.55
    return length_line, 0.65


def _classify_laps(laps: list[dict[str, Any]], lap_length_m: float) -> list[dict[str, Any]]:
    out = []
    for idx, lap in enumerate(laps, start=1):
        line, conf = classify_line(lap, lap_length_m)
        row = dict(lap)
        row['index'] = idx
        row['line'] = line
        row['line_label'] = LINE_LABELS_RU[line]
        row['confidence'] = round(conf, 2)
        out.append(row)
    return out


def _line_counts(laps: list[dict[str, Any]]) -> dict[str, int]:
    counts = {line: 0 for line in LINE_ORDER}
    for lap in laps:
        line = lap.get('line')
        if line in counts:
            counts[line] += 1
    return counts


def _lap_power_stats(
    times: list[Optional[float]],
    speeds_kmh: list[Optional[float]],
    powers: list[Optional[float]],
    lap: dict[str, Any],
) -> Optional[dict[str, float]]:
    start, end = lap['start_idx'], lap['end_idx']
    p_vals = _slice_valid(powers, start, end + 1)
    v_vals = _slice_valid(speeds_kmh, start, end + 1)
    if len(p_vals) < 3 or len(v_vals) < 3:
        return None
    p_mean = _mean(p_vals) or 0.0
    v_mean = _mean(v_vals) or 0.0
    if v_mean < MOVING_SPEED_KMH:
        return None
    v_ms = v_mean / 3.6
    proxy = p_mean / (v_ms ** 3) if v_ms > 0.5 else 0.0
    return {
        'p_mean': p_mean,
        'v_mean': v_mean,
        'drag_proxy': proxy,
        'speed_cv': _cv(v_vals),
    }


def detect_rotations(
    times: list[Optional[float]],
    speeds_kmh: list[Optional[float]],
    powers: list[Optional[float]],
    laps: list[dict[str, Any]],
) -> dict[str, Any]:
    """Classify laps as leader / follower when power is available."""
    power_count = sum(1 for p in powers if p is not None)
    if power_count < MIN_POWER_SAMPLES or not laps:
        return {
            'available': False,
            'reason': 'no_power',
            'leader_laps': 0,
            'follower_laps': 0,
            'unknown_laps': 0,
            'laps': [],
        }

    stats = []
    for lap in laps:
        s = _lap_power_stats(times, speeds_kmh, powers, lap)
        stats.append(s)

    stable_proxies = [
        s['drag_proxy'] for s in stats if s and s['speed_cv'] <= MIN_GROUP_SPEED_CV
    ]
    center = _mean(stable_proxies)
    if center is None or center <= 0:
        all_proxies = [s['drag_proxy'] for s in stats if s]
        center = _mean(all_proxies)
    if center is None or center <= 0:
        return {
            'available': False,
            'reason': 'insufficient_signal',
            'leader_laps': 0,
            'follower_laps': 0,
            'unknown_laps': len(laps),
            'laps': [],
        }

    high = center * DRAFT_PROXY_HIGH_RATIO
    low = center * DRAFT_PROXY_LOW_RATIO

    roles = []
    leader = follower = unknown = 0
    for lap, s in zip(laps, stats):
        if s is None or s['speed_cv'] > MIN_GROUP_SPEED_CV * 1.8:
            role = 'unknown'
            unknown += 1
        elif s['drag_proxy'] >= high:
            role = 'leader'
            leader += 1
        elif s['drag_proxy'] <= low:
            role = 'follower'
            follower += 1
        else:
            role = 'unknown'
            unknown += 1
        roles.append({
            'index': lap['index'],
            'role': role,
            'drag_proxy': round(s['drag_proxy'], 4) if s else None,
            'p_mean': round(s['p_mean'], 1) if s else None,
        })

    return {
        'available': True,
        'reason': '',
        'leader_laps': leader,
        'follower_laps': follower,
        'unknown_laps': unknown,
        'laps': roles,
    }


def _timeline_segments(laps: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Merge consecutive same-line laps into timeline segments for the diagram."""
    if not laps:
        return []
    segments = []
    cur_line = laps[0]['line']
    t_start = laps[0]['t_start']
    t_end = laps[0]['t_end']
    count = 1
    for lap in laps[1:]:
        if lap['line'] == cur_line:
            t_end = lap['t_end']
            count += 1
        else:
            duration = max(0.0, float(t_end) - float(t_start))
            segments.append({
                'line': cur_line,
                'line_label': LINE_LABELS_RU[cur_line],
                't_start': t_start,
                't_end': t_end,
                'duration_s': round(duration, 1),
                'laps': count,
            })
            cur_line = lap['line']
            t_start = lap['t_start']
            t_end = lap['t_end']
            count = 1
    duration = max(0.0, float(t_end) - float(t_start))
    segments.append({
        'line': cur_line,
        'line_label': LINE_LABELS_RU[cur_line],
        't_start': t_start,
        't_end': t_end,
        'duration_s': round(duration, 1),
        'laps': count,
    })
    total = sum(seg['duration_s'] for seg in segments) or 1.0
    for seg in segments:
        pct = 100.0 * seg['duration_s'] / total
        seg['pct'] = round(pct, 2)
        # Locale-safe string for inline CSS width (avoid "12,5%").
        seg['pct_css'] = f'{pct:.2f}'
        seg['color'] = LINE_COLORS.get(seg['line'], '#9ca3af')
    return segments


def build_track_analysis(activity) -> dict[str, Any]:
    """Build track analysis payload for an Activity (or None if not applicable)."""
    empty = {
        'available': False,
        'reason': 'not_track',
        'total_laps': 0,
        'line_counts': {line: 0 for line in LINE_ORDER},
        'line_rows': [],
        'laps': [],
        'timeline': [],
        'rotations': {
            'available': False,
            'reason': 'not_track',
            'leader_laps': 0,
            'follower_laps': 0,
            'unknown_laps': 0,
            'laps': [],
        },
        'lap_length_m': None,
        'duration_s': 0,
    }

    if not getattr(activity, 'is_track', False):
        return empty

    lap_length = getattr(activity, 'track_lap_length_m', None)
    if lap_length is None:
        empty['reason'] = 'no_lap_length'
        return empty

    lap_length_m = float(Decimal(lap_length))
    streams = activity.streams or {}
    times = _as_float_list(streams.get('time') or [])
    speeds = _as_float_list(streams.get('speed') or [])
    distances = _as_float_list(streams.get('distance') or [])
    powers = _as_float_list(streams.get('power') or [])

    if len(times) < 10 or not _stream_has_values(speeds):
        empty['reason'] = 'no_speed'
        empty['lap_length_m'] = lap_length_m
        return empty

    # Align lengths.
    n = min(len(times), len(speeds))
    if distances:
        n = min(n, len(distances))
    if powers:
        n = min(n, len(powers)) if len(powers) >= n else n
    times = times[:n]
    speeds = speeds[:n]
    distances = distances[:n] if distances else []
    if powers and len(powers) >= n:
        powers = powers[:n]
    else:
        powers = [None] * n

    dist_m = _build_distance_m(times, speeds, distances)
    raw_laps = segment_laps(times, speeds, dist_m, lap_length_m)
    laps = _classify_laps(raw_laps, lap_length_m)
    counts = _line_counts(laps)
    timeline = _timeline_segments(laps)
    rotations = detect_rotations(times, speeds, powers, laps)

    t_end = times[-1] if times and times[-1] is not None else 0.0
    line_rows = [
        {
            'line': line,
            'label': LINE_LABELS_RU[line],
            'color': LINE_COLORS[line],
            'laps': counts[line],
            'pct': round(100.0 * counts[line] / len(laps), 1) if laps else 0.0,
        }
        for line in LINE_ORDER
    ]

    return {
        'available': bool(laps),
        'reason': '' if laps else 'no_laps',
        'total_laps': len(laps),
        'line_counts': counts,
        'line_rows': line_rows,
        'laps': laps,
        'timeline': timeline,
        'rotations': rotations,
        'lap_length_m': lap_length_m,
        'duration_s': float(t_end or 0),
    }
