"""Synthetic-stream tests for velodrome track analysis."""

from __future__ import annotations

import math
from decimal import Decimal
from types import SimpleNamespace

from django.test import TestCase

from activities.track_analysis import (
    LINE_BOARD,
    LINE_CORRIDOR,
    LINE_SLOW,
    LINE_STAYER,
    build_track_analysis,
    classify_line,
    detect_rotations,
    segment_laps,
)


def _make_steady_lap_stream(
    *,
    laps: int,
    lap_length_m: float,
    speed_kmh: float,
    amp_kmh: float = 0.0,
    hz: float = 1.0,
    power_leader: int | None = None,
    power_follower: int | None = None,
    leader_every: int = 2,
):
    """Build time/speed/distance[/power] for N laps at nearly constant speed."""
    times = []
    speeds = []
    distances = []
    powers = []
    t = 0.0
    dist = 0.0
    v_ms = speed_kmh / 3.6
    lap_time = lap_length_m / v_ms
    samples_per_lap = max(8, int(lap_time * hz))
    dt = lap_time / samples_per_lap

    for lap_i in range(laps):
        is_leader = (lap_i % leader_every) == 0
        for s in range(samples_per_lap):
            phase = 2 * math.pi * (s / samples_per_lap)
            # Two humps per lap (banking turns).
            v = speed_kmh + amp_kmh * math.sin(2 * phase)
            times.append(round(t, 3))
            speeds.append(round(v, 3))
            distances.append(round(dist, 3))
            if power_leader is not None:
                powers.append(power_leader if is_leader else power_follower)
            t += dt
            dist += (v / 3.6) * dt

    # Close final point.
    times.append(round(t, 3))
    speeds.append(speed_kmh)
    distances.append(round(dist, 3))
    if power_leader is not None:
        powers.append(power_follower if power_follower is not None else power_leader)

    streams = {
        'time': times,
        'speed': speeds,
        'distance': distances,
    }
    if power_leader is not None:
        streams['power'] = powers
    return streams


def _activity(**kwargs):
    defaults = {
        'is_track': True,
        'track_lap_length_m': Decimal('250'),
        'streams': {},
    }
    defaults.update(kwargs)
    return SimpleNamespace(**defaults)


class ClassifyLineTest(TestCase):
    def test_slow_by_speed(self):
        line, conf = classify_line(
            {'l_eff': 250.0, 'v_mean': 18.0, 'amp': 1.0},
            250.0,
        )
        self.assertEqual(line, LINE_SLOW)
        self.assertGreater(conf, 0.5)

    def test_corridor_by_length(self):
        line, _ = classify_line(
            {'l_eff': 250.0, 'v_mean': 40.0, 'amp': 2.0},
            250.0,
        )
        self.assertEqual(line, LINE_CORRIDOR)

    def test_stayer_by_length(self):
        line, _ = classify_line(
            {'l_eff': 265.0, 'v_mean': 42.0, 'amp': 5.0},
            250.0,
        )
        self.assertEqual(line, LINE_STAYER)

    def test_board_by_length(self):
        line, _ = classify_line(
            {'l_eff': 280.0, 'v_mean': 45.0, 'amp': 9.0},
            250.0,
        )
        self.assertEqual(line, LINE_BOARD)


class SegmentLapsTest(TestCase):
    def test_segments_corridor_laps(self):
        streams = _make_steady_lap_stream(
            laps=10,
            lap_length_m=250.0,
            speed_kmh=40.0,
            amp_kmh=1.5,
        )
        dist = streams['distance']
        laps = segment_laps(streams['time'], streams['speed'], dist, 250.0)
        self.assertGreaterEqual(len(laps), 7)
        for lap in laps:
            self.assertGreater(lap['l_eff'], 220)
            self.assertLess(lap['l_eff'], 280)


class BuildTrackAnalysisTest(TestCase):
    def test_not_track(self):
        result = build_track_analysis(_activity(is_track=False))
        self.assertFalse(result['available'])
        self.assertEqual(result['reason'], 'not_track')

    def test_corridor_counts(self):
        streams = _make_steady_lap_stream(
            laps=12,
            lap_length_m=250.0,
            speed_kmh=40.0,
            amp_kmh=1.2,
        )
        result = build_track_analysis(_activity(streams=streams))
        self.assertTrue(result['available'])
        self.assertGreaterEqual(result['total_laps'], 8)
        self.assertGreater(result['line_counts'][LINE_CORRIDOR], result['total_laps'] // 2)
        self.assertFalse(result['rotations']['available'])
        self.assertEqual(result['rotations']['reason'], 'no_power')

    def test_high_line_longer_laps(self):
        # Longer effective distance + larger amp → stayer/board.
        streams = _make_steady_lap_stream(
            laps=10,
            lap_length_m=270.0,
            speed_kmh=42.0,
            amp_kmh=6.0,
        )
        result = build_track_analysis(
            _activity(track_lap_length_m=Decimal('250'), streams=streams),
        )
        self.assertTrue(result['available'])
        high = (
            result['line_counts'][LINE_STAYER]
            + result['line_counts'][LINE_BOARD]
        )
        self.assertGreater(high, 0)

    def test_slow_zone(self):
        streams = _make_steady_lap_stream(
            laps=6,
            lap_length_m=245.0,
            speed_kmh=16.0,
            amp_kmh=0.5,
        )
        result = build_track_analysis(_activity(streams=streams))
        self.assertTrue(result['available'])
        self.assertGreater(result['line_counts'][LINE_SLOW], 0)

    def test_rotations_with_power(self):
        streams = _make_steady_lap_stream(
            laps=12,
            lap_length_m=250.0,
            speed_kmh=40.0,
            amp_kmh=1.0,
            power_leader=280,
            power_follower=160,
            leader_every=2,
        )
        result = build_track_analysis(_activity(streams=streams))
        self.assertTrue(result['available'])
        rot = result['rotations']
        self.assertTrue(rot['available'])
        self.assertGreater(rot['leader_laps'], 0)
        self.assertGreater(rot['follower_laps'], 0)

    def test_no_speed_stream(self):
        result = build_track_analysis(_activity(streams={'time': [0, 1], 'speed': []}))
        self.assertFalse(result['available'])
        self.assertEqual(result['reason'], 'no_speed')

    def test_integrates_speed_without_distance(self):
        streams = _make_steady_lap_stream(
            laps=8,
            lap_length_m=250.0,
            speed_kmh=38.0,
            amp_kmh=1.0,
        )
        del streams['distance']
        result = build_track_analysis(_activity(streams=streams))
        self.assertTrue(result['available'])
        self.assertGreaterEqual(result['total_laps'], 5)


class DetectRotationsTest(TestCase):
    def test_unavailable_without_power(self):
        streams = _make_steady_lap_stream(laps=8, lap_length_m=250.0, speed_kmh=40.0)
        dist = streams['distance']
        laps = segment_laps(streams['time'], streams['speed'], dist, 250.0)
        for i, lap in enumerate(laps, start=1):
            lap['index'] = i
        rot = detect_rotations(
            streams['time'],
            streams['speed'],
            [None] * len(streams['time']),
            laps,
        )
        self.assertFalse(rot['available'])
        self.assertEqual(rot['reason'], 'no_power')
