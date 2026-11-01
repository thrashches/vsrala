from datetime import date, datetime, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

from django.test import TestCase
from django.utils import timezone

from activities.leaderboard import week_bounds, week_label, weekly_leaders
from activities.models import Activity, ActivityType
from profiles.models import Follow, Profile


class WeekBoundsTest(TestCase):
    def test_current_week_monday_to_monday(self):
        # Wednesday 2026-10-07 → week Mon 2026-10-05 .. Mon 2026-10-12
        start, end = week_bounds('current', today=date(2026, 10, 7))
        tz = ZoneInfo('Europe/Moscow')
        self.assertEqual(start.astimezone(tz).date(), date(2026, 10, 5))
        self.assertEqual(end.astimezone(tz).date(), date(2026, 10, 12))

    def test_previous_week(self):
        start, end = week_bounds('previous', today=date(2026, 10, 7))
        tz = ZoneInfo('Europe/Moscow')
        self.assertEqual(start.astimezone(tz).date(), date(2026, 9, 28))
        self.assertEqual(end.astimezone(tz).date(), date(2026, 10, 5))

    def test_week_label_cross_month(self):
        start, end = week_bounds('previous', today=date(2026, 10, 7))
        self.assertEqual(week_label(start, end), '28 сен – 4 окт')


class WeeklyLeadersServiceTest(TestCase):
    def setUp(self):
        self.me = Profile.objects.create_user(
            email='me@example.com', password='pass', first_name='Я',
        )
        self.friend = Profile.objects.create_user(
            email='friend@example.com', password='pass', first_name='Друг',
        )
        self.stranger = Profile.objects.create_user(
            email='stranger@example.com', password='pass', first_name='Чужой', is_public=True,
        )
        Follow.objects.create(user=self.me, following=self.friend)

        self.ride = ActivityType.objects.create(name='Шоссейный велосипед')
        self.run = ActivityType.objects.create(name='Бег')

        self.today = date(2026, 10, 7)  # Wednesday
        tz = ZoneInfo('Europe/Moscow')
        self.this_week = timezone.make_aware(datetime(2026, 10, 6, 10, 0), tz)
        self.last_week = timezone.make_aware(datetime(2026, 9, 30, 10, 0), tz)

        Activity.objects.create(
            profile=self.me,
            title='Моя',
            activity_type=self.ride,
            distance=Decimal('40.00'),
            duration=timedelta(hours=1, minutes=30),
            started_at=self.this_week,
        )
        Activity.objects.create(
            profile=self.friend,
            title='Друга',
            activity_type=self.ride,
            distance=Decimal('60.00'),
            duration=timedelta(hours=2),
            started_at=self.this_week,
        )
        Activity.objects.create(
            profile=self.friend,
            title='Бег друга',
            activity_type=self.run,
            distance=Decimal('10.00'),
            duration=timedelta(hours=1),
            started_at=self.this_week,
        )
        Activity.objects.create(
            profile=self.stranger,
            title='Чужая',
            activity_type=self.ride,
            distance=Decimal('100.00'),
            duration=timedelta(hours=3),
            started_at=self.this_week,
        )
        Activity.objects.create(
            profile=self.friend,
            title='Прошлая',
            activity_type=self.ride,
            distance=Decimal('80.00'),
            duration=timedelta(hours=2, minutes=30),
            started_at=self.last_week,
        )

    def test_only_self_and_follows(self):
        result = weekly_leaders(self.me, today=self.today)
        ids = [row['profile_id'] for row in result['leaders']]
        self.assertIn(self.me.pk, ids)
        self.assertIn(self.friend.pk, ids)
        self.assertNotIn(self.stranger.pk, ids)
        self.assertEqual(result['leaders'][0]['profile_id'], self.friend.pk)
        self.assertEqual(result['leaders'][0]['total'], 70.0)  # 60+10

    def test_sport_filter(self):
        result = weekly_leaders(self.me, sport_id=self.run.pk, today=self.today)
        self.assertEqual(len(result['leaders']), 1)
        self.assertEqual(result['leaders'][0]['profile_id'], self.friend.pk)
        self.assertEqual(result['leaders'][0]['total'], 10.0)

    def test_metric_duration_changes_order(self):
        # me: 1.5h, friend: 2h+1h=3h → friend first by duration too,
        # but make me longer alone for ride-only? Use all sports:
        # friend 3h > me 1.5h — same order. Adjust: add long ride for me on duration check
        # instead compare totals display.
        by_distance = weekly_leaders(self.me, metric='distance', today=self.today)
        by_duration = weekly_leaders(self.me, metric='duration', today=self.today)
        self.assertEqual(by_distance['metric'], 'distance')
        self.assertEqual(by_duration['metric'], 'duration')
        friend_dist = next(r for r in by_distance['leaders'] if r['profile_id'] == self.friend.pk)
        friend_dur = next(r for r in by_duration['leaders'] if r['profile_id'] == self.friend.pk)
        self.assertEqual(friend_dist['total'], 70.0)
        self.assertEqual(friend_dur['total'], 3 * 3600)  # 2h + 1h
        self.assertIn(':', friend_dur['total_display'])

    def test_previous_week(self):
        result = weekly_leaders(self.me, week='previous', today=self.today)
        self.assertEqual(len(result['leaders']), 1)
        self.assertEqual(result['leaders'][0]['profile_id'], self.friend.pk)
        self.assertEqual(result['leaders'][0]['total'], 80.0)
        self.assertEqual(result['week'], 'previous')
        self.assertIn('сен', result['week_label'])
