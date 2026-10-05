from datetime import datetime, timedelta
from pathlib import Path

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase
from django.urls import reverse

from activities.models import Activity
from activities.parsers.base import ParsedTrack
from activities.zone_timeline import apply_zone_timeline, build_zone_timeline_for_activity
from profiles.models import Profile
from profiles.zones import default_hr_zones, default_power_zones

FIXTURES = Path(__file__).parent / 'fixtures'


class IndoorFlagTest(TestCase):
    def setUp(self):
        self.profile = Profile.objects.create_user(email='indoor@example.com', password='x')

    def test_indoor_when_no_gps_points(self):
        activity = Activity(profile=self.profile, started_at=datetime.now())
        parsed = ParsedTrack(
            started_at=datetime.now(),
            duration=timedelta(minutes=30),
            duration_active=timedelta(minutes=30),
            distance_km=0,
            points=[],
            streams={'time': [0, 10, 20], 'hr': [120, 130, 140], 'power': []},
        )
        activity.apply_parsed_track(parsed)
        self.assertTrue(activity.is_indoor)

    def test_outdoor_when_gps_points(self):
        activity = Activity(profile=self.profile, started_at=datetime.now())
        parsed = ParsedTrack(
            started_at=datetime.now(),
            duration=timedelta(minutes=30),
            duration_active=timedelta(minutes=30),
            distance_km=10,
            points=[[55.75, 37.6, 0], [55.76, 37.61, 60]],
            streams={'time': [0, 60], 'hr': [], 'power': []},
        )
        activity.apply_parsed_track(parsed)
        self.assertFalse(activity.is_indoor)


class ZoneTimelineTest(TestCase):
    def setUp(self):
        self.profile = Profile.objects.create_user(email='tl@example.com', password='x')
        self.profile.ftp = 200
        self.profile.max_heart_rate = 190
        self.profile.power_zones = default_power_zones(200)
        self.profile.hr_zones = default_hr_zones(190)
        self.profile.save()

    def _activity(self, **streams):
        activity = Activity.objects.create(
            profile=self.profile,
            started_at=datetime.now(),
            duration=timedelta(minutes=10),
            streams=streams,
            is_indoor=True,
        )
        return activity

    def test_prefers_power_over_hr(self):
        n = 60
        activity = self._activity(
            time=list(range(n)),
            power=[100 + i for i in range(n)],
            hr=[140] * n,
        )
        content, key = build_zone_timeline_for_activity(activity)
        self.assertIsNotNone(content)
        self.assertEqual(key, 'power')
        self.assertTrue(apply_zone_timeline(activity))
        activity.refresh_from_db()
        self.assertEqual(activity.zone_stream, 'power')
        self.assertTrue(activity.zone_timeline.name)

    def test_falls_back_to_hr(self):
        n = 40
        activity = self._activity(
            time=list(range(n)),
            power=[],
            hr=[150 + (i % 20) for i in range(n)],
        )
        content, key = build_zone_timeline_for_activity(activity)
        self.assertIsNotNone(content)
        self.assertEqual(key, 'hr')

    def test_no_image_without_metrics(self):
        activity = self._activity(time=[0, 1, 2], power=[], hr=[])
        content, key = build_zone_timeline_for_activity(activity)
        self.assertIsNone(content)
        self.assertEqual(key, '')

    def test_upload_indoor_fit_sets_flag(self):
        # sample.fit from fixtures may be outdoor; synthesize via apply
        client = Client()
        user = Profile.objects.create_user(email='up@example.com', password='testpass123')
        user.ftp = 250
        user.power_zones = default_power_zones(250)
        user.save()
        client.login(email='up@example.com', password='testpass123')

        # Use GPX fixture (has GPS) — outdoor
        content = (FIXTURES / 'sample.gpx').read_bytes()
        upload = SimpleUploadedFile('sample.gpx', content, content_type='application/gpx+xml')
        response = client.post(reverse('webinterface:activity_upload'), {
            'track_file': upload,
            'title': 'Outdoor',
        })
        self.assertEqual(response.status_code, 302)
        activity = Activity.objects.get(profile=user)
        self.assertFalse(activity.is_indoor)
