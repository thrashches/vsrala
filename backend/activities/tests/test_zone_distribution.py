from django.test import SimpleTestCase

from activities.zone_distribution import (
    compute_zone_distribution,
    format_duration,
    stream_has_data,
)
from profiles.zones import default_hr_zones


class StreamHasDataTests(SimpleTestCase):
    def test_empty(self):
        self.assertFalse(stream_has_data([]))
        self.assertFalse(stream_has_data(None))
        self.assertFalse(stream_has_data([None, None]))

    def test_has_values(self):
        self.assertTrue(stream_has_data([None, 120, None]))


class FormatDurationTests(SimpleTestCase):
    def test_seconds(self):
        self.assertEqual(format_duration(0), '0 с.')
        self.assertEqual(format_duration(45), '45 с.')

    def test_minutes(self):
        self.assertEqual(format_duration(186), '3:06')

    def test_hours(self):
        self.assertEqual(format_duration(3661), '1:01:01')


class ZoneDistributionTests(SimpleTestCase):
    def setUp(self):
        self.zones = default_hr_zones(190)

    def test_order_highest_first(self):
        # All samples in Z1 (Recovery)
        z1_max = self.zones[0]['max']
        values = [z1_max] * 10
        times = list(range(0, 100, 10))
        rows = compute_zone_distribution(values, times, self.zones)
        self.assertEqual(len(rows), 7)
        self.assertEqual(rows[0]['label'], 'Z7')
        self.assertEqual(rows[-1]['label'], 'Z1')
        self.assertAlmostEqual(rows[-1]['percent'], 100.0)
        self.assertTrue(rows[-1]['has_time'])
        self.assertFalse(rows[0]['has_time'])

    def test_split_across_zones(self):
        z1_hi = self.zones[0]['max']
        z2_lo = self.zones[1]['min']
        # 5 samples in Z1, 5 in Z2, 10s each → equal time
        values = [z1_hi] * 5 + [z2_lo] * 5
        times = list(range(0, 100, 10))
        rows = compute_zone_distribution(values, times, self.zones)
        by_label = {r['label']: r for r in rows}
        self.assertAlmostEqual(by_label['Z1']['percent'], 50.0, places=0)
        self.assertAlmostEqual(by_label['Z2']['percent'], 50.0, places=0)

    def test_range_format(self):
        rows = compute_zone_distribution([100], [0], self.zones)
        by_label = {r['label']: r for r in rows}
        self.assertTrue(by_label['Z7']['range'].endswith('+'))
        self.assertIn(' - ', by_label['Z1']['range'])
        self.assertIn(' - ', by_label['Z3']['range'])
        self.assertEqual(by_label['Z1']['percent_display'][-1], '%')
        self.assertNotIn(',', by_label['Z1']['percent_display'])
