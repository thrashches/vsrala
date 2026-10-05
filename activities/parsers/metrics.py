"""Shared metric helpers for track parsers."""
from __future__ import annotations

import math
from typing import Optional, Sequence


def elevation_stats(elevations: Sequence[Optional[float]]) -> tuple[
    Optional[float], Optional[float], Optional[float], Optional[float]
]:
    """Return (gain, loss, min, max) from altitude samples."""
    gain = 0.0
    loss = 0.0
    valid = [e for e in elevations if e is not None]
    for i in range(1, len(elevations)):
        prev, cur = elevations[i - 1], elevations[i]
        if prev is None or cur is None:
            continue
        delta = cur - prev
        if delta > 0:
            gain += delta
        elif delta < 0:
            loss += -delta
    elev_min = round(min(valid), 1) if valid else None
    elev_max = round(max(valid), 1) if valid else None
    return (
        round(gain, 1) if gain else None,
        round(loss, 1) if loss else None,
        elev_min,
        elev_max,
    )


def speed_averages(
    distance_km: float,
    duration_seconds: float,
    moving_seconds: float,
) -> tuple[Optional[float], Optional[float]]:
    """Return (avg_speed, avg_moving_speed) in km/h."""
    avg_speed = None
    avg_moving = None
    if distance_km > 0 and duration_seconds > 0:
        avg_speed = round(distance_km / (duration_seconds / 3600), 2)
    if distance_km > 0 and moving_seconds > 0:
        avg_moving = round(distance_km / (moving_seconds / 3600), 2)
    return avg_speed, avg_moving


def normalized_power_from_stream(
    powers: Sequence[Optional[int]],
    times_sec: Sequence[float],
) -> Optional[int]:
    """Coggan NP: 4th-root of mean of (30s rolling avg)^4."""
    samples: list[tuple[float, float]] = []
    for i, p in enumerate(powers):
        if p is None:
            continue
        t = times_sec[i] if i < len(times_sec) else float(i)
        samples.append((t, float(p)))
    if len(samples) < 2:
        if len(samples) == 1:
            return int(round(samples[0][1]))
        return None

    # Build dense 1 Hz series by forward-fill between samples
    t0 = samples[0][0]
    t1 = samples[-1][0]
    if t1 <= t0:
        return int(round(sum(p for _, p in samples) / len(samples)))

    duration = int(math.floor(t1 - t0)) + 1
    if duration < 1:
        return None

    series = [0.0] * duration
    idx = 0
    for sec in range(duration):
        t = t0 + sec
        while idx + 1 < len(samples) and samples[idx + 1][0] <= t:
            idx += 1
        series[sec] = samples[idx][1]

    window = 30
    if len(series) < window:
        mean_p = sum(series) / len(series)
        return int(round(mean_p))

    rolling: list[float] = []
    window_sum = sum(series[:window])
    rolling.append(window_sum / window)
    for i in range(window, len(series)):
        window_sum += series[i] - series[i - window]
        rolling.append(window_sum / window)

    fourth = sum(v ** 4 for v in rolling) / len(rolling)
    return int(round(fourth ** 0.25))


def compute_tss(
    normalized_power: Optional[int],
    moving_seconds: float,
    ftp: Optional[int],
) -> Optional[float]:
    """TSS = (t * NP * IF) / (FTP * 3600) * 100, IF = NP / FTP."""
    if not normalized_power or not ftp or ftp <= 0 or moving_seconds <= 0:
        return None
    intensity = normalized_power / ftp
    tss = (moving_seconds * normalized_power * intensity) / (ftp * 3600) * 100
    return round(tss, 1)


def cadence_stats(
    cadences: Sequence[Optional[int]],
) -> tuple[Optional[int], Optional[int]]:
    vals = [c for c in cadences if c is not None and c > 0]
    if not vals:
        return None, None
    return int(sum(vals) / len(vals)), max(vals)
