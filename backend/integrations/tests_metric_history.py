from datetime import date
from decimal import Decimal

from django.test import TestCase

from integrations.metric_history import (
    ingest_garmin_vo2max,
    ingest_garmin_weight,
    ingest_intervals_wellness,
)
from profiles.models import Profile, ProfileMetricSample


class MetricHistoryIngestTests(TestCase):
    def setUp(self):
        self.profile = Profile.objects.create_user(
            email='ingest@example.com', password='secret123',
        )

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
