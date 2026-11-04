from django.test import SimpleTestCase, TestCase

from activities.activity_types import activity_uses_pace, ensure_activity_type
from activities.models import ActivityType
from activities.pace import format_pace, format_pace_display, speed_to_pace_seconds


class PaceFormatTests(SimpleTestCase):
    def test_speed_to_pace_seconds(self):
        self.assertAlmostEqual(speed_to_pace_seconds(12), 300.0)
        self.assertIsNone(speed_to_pace_seconds(0))
        self.assertIsNone(speed_to_pace_seconds(None))

    def test_format_pace(self):
        self.assertEqual(format_pace(12), '5:00')
        self.assertEqual(format_pace(10), '6:00')
        self.assertEqual(format_pace(14.4), '4:10')
        self.assertIsNone(format_pace(0.1))

    def test_format_pace_display(self):
        self.assertEqual(format_pace_display(12), '5:00 /км')


class ActivityUsesPaceTests(TestCase):
    def test_foot_sports(self):
        for slug in ('running', 'walking', 'skiing'):
            at = ActivityType.objects.get(slug=slug)
            self.assertTrue(activity_uses_pace(at), slug)

    def test_cycling_and_none(self):
        ride = ActivityType.objects.get(slug='road_cycling')
        self.assertFalse(activity_uses_pace(ride))
        self.assertFalse(activity_uses_pace(None))
        custom = ensure_activity_type('Кастомный спорт')
        self.assertFalse(activity_uses_pace(custom))
