from pathlib import Path

from django.test import TestCase

from activities.parsers import TrackParseError, parse_track
from activities.parsers.metrics import compute_tss, elevation_stats, normalized_power_from_stream

FIXTURES = Path(__file__).parent / 'fixtures'


class GpxParserTest(TestCase):
    def test_parse_sample_gpx(self):
        parsed = parse_track(FIXTURES / 'sample.gpx')
        self.assertGreater(parsed.distance_km, 0)
        self.assertEqual(len(parsed.points), 5)
        self.assertEqual(len(parsed.points[0]), 3)
        self.assertEqual(parsed.points[0][2], 0)
        self.assertEqual(parsed.avg_hr, 147)
        self.assertEqual(parsed.max_hr, 152)
        self.assertIsNotNone(parsed.avg_speed)
        self.assertIsNotNone(parsed.avg_moving_speed)
        self.assertTrue(parsed.streams.get('hr'))
        self.assertEqual(len(parsed.streams['time']), len(parsed.streams['hr']))
        self.assertEqual(parsed.streams['time'][0], 0)
        self.assertIsNotNone(parsed.elevation_min)
        self.assertIsNotNone(parsed.elevation_max)
        self.assertIsNotNone(parsed.elevation_gain)

    def test_parse_by_filename_hint(self):
        with open(FIXTURES / 'sample.gpx', 'rb') as f:
            parsed = parse_track(f, filename='ride.gpx')
        self.assertGreater(len(parsed.points), 0)


class FitParserTest(TestCase):
    def test_parse_sample_fit(self):
        parsed = parse_track(FIXTURES / 'sample.fit')
        self.assertGreater(parsed.distance_km, 0)
        self.assertGreater(len(parsed.points), 10)
        self.assertIsNotNone(parsed.started_at)
        self.assertTrue(parsed.streams.get('speed') or parsed.streams.get('hr'))
        self.assertIn('time', parsed.streams)
        self.assertEqual(len(parsed.streams['time']), len(parsed.streams.get('speed') or parsed.streams.get('hr')))
        self.assertGreaterEqual(parsed.streams['time'][-1], parsed.streams['time'][0])
        self.assertIsNotNone(parsed.avg_moving_speed)


class MetricsHelpersTest(TestCase):
    def test_elevation_stats(self):
        gain, loss, elev_min, elev_max = elevation_stats([100.0, 120.0, 110.0, 130.0])
        self.assertEqual(gain, 40.0)
        self.assertEqual(loss, 10.0)
        self.assertEqual(elev_min, 100.0)
        self.assertEqual(elev_max, 130.0)

    def test_normalized_power_constant(self):
        powers = [200] * 60
        times = list(range(60))
        np_val = normalized_power_from_stream(powers, times)
        self.assertEqual(np_val, 200)

    def test_compute_tss(self):
        # 1 hour at NP=FTP → TSS ≈ 100
        tss = compute_tss(250, 3600, 250)
        self.assertEqual(tss, 100.0)
        self.assertIsNone(compute_tss(250, 3600, None))


class ParseTrackDispatchTest(TestCase):
    def test_unsupported_extension(self):
        with self.assertRaises(TrackParseError):
            parse_track('file.txt', filename='file.txt')
