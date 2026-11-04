from datetime import datetime, timedelta, timezone
from decimal import Decimal

from django.test import TestCase

from activities.models import Activity, ActivityType
from activities.user_stats import build_user_stats
from profiles.models import Profile


class UserStatsTests(TestCase):
    def setUp(self):
        self.profile = Profile.objects.create_user(
            email='stats@example.com', password='secret123',
        )
        self.cycling, _ = ActivityType.objects.get_or_create(
            slug='road_cycling',
            defaults={'name': 'Шоссейный велосипед', 'sort_order': 10},
        )
        self.running, _ = ActivityType.objects.get_or_create(
            slug='running',
            defaults={'name': 'Бег', 'sort_order': 50},
        )

    def test_by_type_and_averages(self):
        Activity.objects.create(
            profile=self.profile,
            title='Ride 1',
            activity_type=self.cycling,
            started_at=datetime(2026, 5, 1, 10, 0, tzinfo=timezone.utc),
            distance=Decimal('40'),
            duration=timedelta(hours=2),
            elevation_gain=Decimal('200'),
            avg_moving_speed=Decimal('20'),
            tss=Decimal('80'),
        )
        Activity.objects.create(
            profile=self.profile,
            title='Ride 2',
            activity_type=self.cycling,
            started_at=datetime(2026, 5, 2, 10, 0, tzinfo=timezone.utc),
            distance=Decimal('20'),
            duration=timedelta(hours=1),
            elevation_gain=Decimal('100'),
            avg_moving_speed=Decimal('20'),
            tss=Decimal('40'),
        )
        Activity.objects.create(
            profile=self.profile,
            title='Run',
            activity_type=self.running,
            started_at=datetime(2026, 6, 1, 8, 0, tzinfo=timezone.utc),
            distance=Decimal('10'),
            duration=timedelta(minutes=50),
            elevation_gain=Decimal('40'),
            avg_moving_speed=Decimal('12'),
        )

        stats = build_user_stats(
            Activity.objects.filter(profile=self.profile),
            year=2026,
        )
        self.assertEqual(stats['year'], 2026)
        self.assertEqual(stats['totals']['count'], 3)
        self.assertEqual(stats['totals']['distance'], '70')
        self.assertEqual(len(stats['by_type']), 2)

        cycling = next(r for r in stats['by_type'] if r['slug'] == 'road_cycling')
        self.assertEqual(cycling['count'], 2)
        self.assertEqual(cycling['averages']['distance'], '30')
        self.assertTrue(cycling['averages']['speed_display'])

        running = next(r for r in stats['by_type'] if r['slug'] == 'running')
        self.assertEqual(running['count'], 1)
        self.assertTrue(running['averages']['pace_display'])
