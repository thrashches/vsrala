from datetime import date, timedelta
from decimal import Decimal
from unittest.mock import MagicMock

from django.test import TestCase
from django.utils import timezone as dj_timezone

from integrations.garmin_client import GarminApiError
from integrations.metric_history import (
    _metric_window,
    _sync_garmin_weight,
    _UNSUPPORTED_GARMIN_METRICS,
    ingest_garmin_vo2max,
    ingest_garmin_weight,
    ingest_intervals_wellness,
)
from profiles.models import Profile, ProfileMetricSample


class MetricWindowTests(TestCase):
    def test_incremental_window_uses_max_cap_not_forced_90d(self):
        today = dj_timezone.localdate()
        last_synced = dj_timezone.now()
        oldest, newest = _metric_window(initial=False, last_synced_at=last_synced)
        self.assertEqual(newest, today)
        self.assertGreaterEqual(oldest, today - timedelta(days=7))
        self.assertLessEqual(oldest, today)

    def test_initial_window_is_long(self):
        today = dj_timezone.localdate()
        oldest, newest = _metric_window(initial=True, last_synced_at=None)
        self.assertEqual(newest, today)
        self.assertLessEqual(oldest, today - timedelta(days=365))


class MetricHistoryIngestTests(TestCase):
    def setUp(self):
        self.profile = Profile.objects.create_user(
            email='ingest@example.com', password='secret123',
        )
        _UNSUPPORTED_GARMIN_METRICS.clear()

    def test_ingest_garmin_weight_grams(self):
        raw = {
            'dateWeightList': [
                {'calendarDate': '2026-01-05', 'weight': 72500},
                {'date': '2026-01-06', 'weight': 71.8},
            ],
        }
        written = ingest_garmin_weight(self.profile, raw)
        self.assertEqual(written, 2)
        values = list(
            ProfileMetricSample.objects.filter(
                profile=self.profile,
                metric=ProfileMetricSample.Metric.WEIGHT,
            ).order_by('recorded_on').values_list('value', flat=True)
        )
        self.assertEqual(values[0], Decimal('72.500'))
        self.assertEqual(values[1], Decimal('71.800'))

    def test_ingest_garmin_vo2max_prefers_cycling(self):
        raw = [
            {
                'calendarDate': '2026-03-01',
                'generic': {'vo2MaxValue': 48},
                'cycling': {'vo2MaxValue': 55},
            },
        ]
        written = ingest_garmin_vo2max(self.profile, raw)
        self.assertEqual(written, 1)
        sample = ProfileMetricSample.objects.get()
        self.assertEqual(sample.value, Decimal('55'))
        self.assertEqual(sample.recorded_on, date(2026, 3, 1))

    def test_ingest_intervals_wellness(self):
        rows = [
            {'id': '2026-01-10', 'weight': 70.5, 'vo2max': 50},
            {'id': '2026-01-11', 'weight': None},
        ]
        weight_n, vo2_n = ingest_intervals_wellness(self.profile, rows)
        self.assertEqual(weight_n, 1)
        self.assertEqual(vo2_n, 1)
        self.assertEqual(ProfileMetricSample.objects.count(), 2)

    def test_garmin_weight_404_marked_unsupported(self):
        client = MagicMock()
        client.get_weight_range.side_effect = GarminApiError('missing', status_code=404)
        start = date(2026, 1, 1)
        end = date(2026, 1, 2)
        self.assertEqual(_sync_garmin_weight(self.profile, client, start, end), 0)
        self.assertIn('weight', _UNSUPPORTED_GARMIN_METRICS)
        self.assertEqual(_sync_garmin_weight(self.profile, client, start, end), 0)
        self.assertEqual(client.get_weight_range.call_count, 1)
