from datetime import date, datetime, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

from django.test import TestCase
from django.utils import timezone

from activities.models import Activity
from activities.year_stats import aggregate_year, available_years, build_year_stats, year_bounds
from profiles.models import Profile


class YearBoundsTest(TestCase):
    def test_calendar_year_in_project_tz(self):
        start, end = year_bounds(2025)
        tz = ZoneInfo('Europe/Moscow')
        self.assertEqual(start.astimezone(tz), timezone.make_aware(datetime(2025, 1, 1), tz))
        self.assertEqual(end.astimezone(tz), timezone.make_aware(datetime(2026, 1, 1), tz))


class YearStatsServiceTest(TestCase):
    def setUp(self):
        self.user = Profile.objects.create_user(
            email='rider@example.com', password='pass', first_name='Райдер',
        )
        self.tz = ZoneInfo('Europe/Moscow')
        self.today = date(2026, 10, 5)

        Activity.objects.create(
            profile=self.user,
            title='2026 A',
            distance=Decimal('40.00'),
            duration=timedelta(hours=2),
            elevation_gain=Decimal('100.0'),
            started_at=timezone.make_aware(datetime(2026, 3, 10, 10, 0), self.tz),
        )
        Activity.objects.create(
            profile=self.user,
            title='2026 B',
            distance=Decimal('20.50'),
            duration=timedelta(hours=1, minutes=30),
            elevation_gain=None,
            started_at=timezone.make_aware(datetime(2026, 6, 1, 10, 0), self.tz),
        )
        Activity.objects.create(
            profile=self.user,
            title='2025',
            distance=Decimal('100.00'),
            duration=timedelta(hours=5),
            elevation_gain=Decimal('350.5'),
            started_at=timezone.make_aware(datetime(2025, 8, 15, 10, 0), self.tz),
        )

    def test_available_years_includes_current_and_past(self):
        qs = Activity.objects.filter(profile=self.user)
        years = available_years(qs, today=self.today)
        self.assertEqual(years, [2026, 2025])

    def test_aggregate_year_sums_and_handles_null_elevation(self):
        qs = Activity.objects.filter(profile=self.user)
        stats_2026 = aggregate_year(qs, 2026)
        self.assertEqual(stats_2026['distance'], '60.5')
        self.assertEqual(stats_2026['distance_display'], '60.5 км')
        self.assertEqual(stats_2026['duration_display'], '3:30:00')
        self.assertEqual(stats_2026['elevation'], '100')
        self.assertEqual(stats_2026['count'], 2)

        stats_2025 = aggregate_year(qs, 2025)
        self.assertEqual(stats_2025['distance'], '100')
        self.assertEqual(stats_2025['elevation'], '350.5')
        self.assertEqual(stats_2025['count'], 1)

    def test_build_year_stats_defaults_to_current_year(self):
        qs = Activity.objects.filter(profile=self.user)
        result = build_year_stats(qs, today=self.today)
        self.assertEqual(result['selected_year'], 2026)
        self.assertEqual(result['years'], [2026, 2025])
        self.assertEqual(result['by_year'][2026]['count'], 2)
        self.assertEqual(result['by_year'][2025]['count'], 1)

    def test_empty_year_returns_zeros(self):
        qs = Activity.objects.filter(profile=self.user)
        stats = aggregate_year(qs, 2024)
        self.assertEqual(stats['distance'], '0')
        self.assertEqual(stats['duration_display'], '0:00')
        self.assertEqual(stats['elevation'], '0')
        self.assertEqual(stats['count'], 0)
