from datetime import date
from decimal import Decimal

from django.test import TestCase
from django.utils import timezone

from profiles.metrics import metric_series, upsert_metric_sample
from profiles.models import Profile, ProfileMetricSample


class ProfileMetricSampleTests(TestCase):
    def setUp(self):
        self.profile = Profile.objects.create_user(
            email='metrics@example.com', password='secret123',
        )

    def test_upsert_creates_and_updates(self):
        sample = upsert_metric_sample(
            self.profile,
            metric=ProfileMetricSample.Metric.WEIGHT,
            recorded_on=date(2026, 1, 10),
            value='72.5',
            source=ProfileMetricSample.Source.GARMIN,
        )
        self.assertIsNotNone(sample)
        self.assertEqual(sample.value, Decimal('72.5'))
        self.assertEqual(ProfileMetricSample.objects.count(), 1)

        upsert_metric_sample(
            self.profile,
            metric=ProfileMetricSample.Metric.WEIGHT,
            recorded_on=date(2026, 1, 10),
            value='73.0',
            source=ProfileMetricSample.Source.GARMIN,
        )
        self.assertEqual(ProfileMetricSample.objects.count(), 1)
        sample.refresh_from_db()
        self.assertEqual(sample.value, Decimal('73.0'))

    def test_ftp_updates_profile(self):
        upsert_metric_sample(
            self.profile,
            metric=ProfileMetricSample.Metric.FTP,
            recorded_on=timezone.localdate(),
            value=250,
            source=ProfileMetricSample.Source.GARMIN,
        )
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.ftp, 250)

    def test_metric_series_prefers_garmin(self):
        day = date(2026, 2, 1)
        upsert_metric_sample(
            self.profile,
            metric=ProfileMetricSample.Metric.VO2MAX,
            recorded_on=day,
            value=48,
            source=ProfileMetricSample.Source.ACTIVITY,
            update_profile_ftp=False,
        )
        upsert_metric_sample(
            self.profile,
            metric=ProfileMetricSample.Metric.VO2MAX,
            recorded_on=day,
            value=52,
            source=ProfileMetricSample.Source.GARMIN,
            update_profile_ftp=False,
        )
        series = metric_series(self.profile, ProfileMetricSample.Metric.VO2MAX)
        self.assertEqual(series, [{'date': '2026-02-01', 'value': 52.0}])

    def test_invalid_value_ignored(self):
        self.assertIsNone(
            upsert_metric_sample(
                self.profile,
                metric=ProfileMetricSample.Metric.FTP,
                recorded_on=timezone.localdate(),
                value=0,
                source=ProfileMetricSample.Source.PROFILE,
            )
        )
        self.assertEqual(ProfileMetricSample.objects.count(), 0)
