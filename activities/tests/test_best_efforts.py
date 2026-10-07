from types import SimpleNamespace

from django.test import SimpleTestCase

from activities.best_efforts import (
    best_distance_efforts,
    best_power_efforts,
    build_best_efforts,
    format_effort_duration,
    format_power_window,
)


class FormatHelpersTests(SimpleTestCase):
    def test_effort_duration(self):
        self.assertEqual(format_effort_duration(45), '45 с')
        self.assertEqual(format_effort_duration(125), '2:05')

    def test_power_window(self):
        self.assertEqual(format_power_window(5), '5 с')
        self.assertEqual(format_power_window(60), '1 мин')
        self.assertEqual(format_power_window(1200), '20 мин')


class BestDistanceEffortsTests(SimpleTestCase):
    def test_constant_speed_1km(self):
        # 36 km/h → 1 km in 100 seconds
        n = 200
        times = list(range(n))
        speeds = [36.0] * n
        rows = best_distance_efforts({'time': times, 'speed': speeds}, targets_km=(1, 5))
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['distance_km'], 1)
        self.assertAlmostEqual(rows[0]['seconds'], 100.0, delta=2.0)
        self.assertAlmostEqual(rows[0]['speed_kmh'], 36.0, delta=1.0)
        self.assertIn('км/ч', rows[0]['speed_display'])

    def test_skips_targets_beyond_total(self):
        times = list(range(50))
        speeds = [36.0] * 50  # ~0.5 km
        rows = best_distance_efforts({'time': times, 'speed': speeds}, targets_km=(1, 5))
        self.assertEqual(rows, [])

    def test_faster_middle_segment_wins(self):
        # Slow, then fast 1km, then slow
        times = []
        speeds = []
        t = 0
        # 0.2 km at 18 km/h (40s)
        for _ in range(40):
            times.append(t)
            speeds.append(18.0)
            t += 1
        # 1.2 km at 36 km/h (120s) — best 1km ~100s
        for _ in range(120):
            times.append(t)
            speeds.append(36.0)
            t += 1
        # more slow
        for _ in range(40):
            times.append(t)
            speeds.append(18.0)
            t += 1
        rows = best_distance_efforts({'time': times, 'speed': speeds}, targets_km=(1,))
        self.assertEqual(len(rows), 1)
        self.assertAlmostEqual(rows[0]['seconds'], 100.0, delta=3.0)

    def test_fallback_to_track_points(self):
        # ~1 km north at ~111 km per degree latitude
        # Move 0.01 degrees ≈ 1.11 km
        points = []
        for i in range(101):
            lat = 55.0 + 0.01 * (i / 100)
            points.append([lat, 37.0, float(i * 10)])  # 1000 seconds total
        rows = best_distance_efforts({'time': [], 'speed': []}, track_points=points, targets_km=(1,))
        self.assertEqual(len(rows), 1)
        self.assertGreater(rows[0]['seconds'], 0)


class BestPowerEffortsTests(SimpleTestCase):
    def test_peak_window(self):
        # 30s at 100W, then 10s at 300W, then 30s at 100W
        powers = [100] * 30 + [300] * 10 + [100] * 30
        times = list(range(len(powers)))
        rows = best_power_efforts({'power': powers, 'time': times}, windows_sec=(5, 15, 60))
        by_w = {r['window_sec']: r['watts'] for r in rows}
        self.assertEqual(by_w[5], 300)
        # 10s @ 300 + 5s @ 100 → 233 W
        self.assertEqual(by_w[15], 233)
        self.assertIn(60, by_w)
        self.assertNotIn(120, by_w)  # longer than series - we only pass 5,15,60 and 60 fits (70 samples)

    def test_empty_power(self):
        self.assertEqual(best_power_efforts({'power': [], 'time': []}), [])
        self.assertEqual(best_power_efforts({'power': [None, None], 'time': [0, 1]}), [])

    def test_skips_windows_longer_than_series(self):
        powers = [200] * 20
        times = list(range(20))
        rows = best_power_efforts({'power': powers, 'time': times}, windows_sec=(5, 30, 60))
        self.assertEqual([r['window_sec'] for r in rows], [5])


class BuildBestEffortsTests(SimpleTestCase):
    def test_build(self):
        activity = SimpleNamespace(
            streams={
                'time': list(range(120)),
                'speed': [36.0] * 120,
                'power': [150] * 60 + [250] * 60,
            },
            track_points=[],
        )
        result = build_best_efforts(activity)
        self.assertTrue(result['has_distance_efforts'])
        self.assertTrue(result['has_power_efforts'])
        self.assertEqual(result['distance_efforts'][0]['distance_km'], 1)
