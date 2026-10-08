from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from PIL import Image

from activities.map_preview import (
    IMG_HEIGHT,
    MAX_TRACK_HEIGHT_RATIO,
    apply_map_preview,
    build_map_preview_for_activity,
    render_map_preview_image,
    _choose_zoom,
    _lat_to_world_y,
    _lon_to_world_x,
    _track_span_px,
)
from activities.models import Activity
from activities.parsers.base import ParsedTrack
from profiles.models import Profile

FIXTURES = Path(__file__).parent / 'fixtures'


def _fake_tile(z, x, y, cache):
    key = (z, x, y)
    if key not in cache:
        cache[key] = Image.new('RGB', (256, 256), (200, 210, 220))
    return cache[key]


class MapPreviewRenderTest(TestCase):
    def test_renders_for_valid_track(self):
        img = render_map_preview_image([
            [55.75, 37.60, 0],
            [55.76, 37.61, 60],
            [55.77, 37.62, 120],
        ], use_tiles=False)
        self.assertIsNotNone(img)
        self.assertEqual(img.size, (960, 416))

    def test_none_for_single_point(self):
        self.assertIsNone(render_map_preview_image([[55.75, 37.60]], use_tiles=False))

    def test_none_for_empty(self):
        self.assertIsNone(render_map_preview_image([], use_tiles=False))
        self.assertIsNone(render_map_preview_image(None, use_tiles=False))

    def test_track_height_at_most_half_image(self):
        pts = [
            [55.7500, 37.6000],
            [55.7510, 37.6010],
            [55.7520, 37.6020],
        ]
        lats = [p[0] for p in pts]
        lons = [p[1] for p in pts]
        min_lat, max_lat = min(lats), max(lats)
        min_lon, max_lon = min(lons), max(lons)
        zoom = _choose_zoom(min_lat, max_lat, min_lon, max_lon)
        min_x, max_x, min_y, max_y = _track_span_px(min_lat, max_lat, min_lon, max_lon, zoom)
        track_h = max_y - min_y
        self.assertLessEqual(track_h, IMG_HEIGHT * MAX_TRACK_HEIGHT_RATIO + 1e-6)

    def test_zoom_centers_track(self):
        pts = [[55.75, 37.60], [55.76, 37.61]]
        img = render_map_preview_image(pts, use_tiles=False)
        self.assertIsNotNone(img)
        # Start/end should land inside the image (with zoom-out margin).
        zoom = _choose_zoom(55.75, 55.76, 37.60, 37.61)
        min_x, max_x, min_y, max_y = _track_span_px(55.75, 55.76, 37.60, 37.61, zoom)
        cx = (min_x + max_x) / 2
        cy = (min_y + max_y) / 2
        left = cx - 960 / 2
        top = cy - 416 / 2
        sx = _lon_to_world_x(37.60, zoom) - left
        sy = _lat_to_world_y(55.75, zoom) - top
        self.assertGreaterEqual(sx, 0)
        self.assertLessEqual(sx, 960)
        self.assertGreaterEqual(sy, 0)
        self.assertLessEqual(sy, 416)


@override_settings(MEDIA_ROOT='/tmp/vsrala_test_media_map_preview')
class MapPreviewApplyTest(TestCase):
    def setUp(self):
        self.profile = Profile.objects.create_user(email='map@example.com', password='x')

    @patch('activities.map_preview._fetch_tile', side_effect=_fake_tile)
    def test_applies_when_track_points_present(self, _mock):
        activity = Activity.objects.create(
            profile=self.profile,
            started_at=datetime.now(),
            duration=timedelta(minutes=10),
            track_points=[[55.75, 37.6, 0], [55.76, 37.61, 60]],
        )
        self.assertTrue(apply_map_preview(activity))
        activity.refresh_from_db()
        self.assertTrue(activity.map_preview.name)
        content = build_map_preview_for_activity(activity)
        self.assertIsNotNone(content)

    def test_no_preview_without_gps(self):
        activity = Activity.objects.create(
            profile=self.profile,
            started_at=datetime.now(),
            duration=timedelta(minutes=10),
            track_points=[],
            is_indoor=True,
        )
        self.assertFalse(apply_map_preview(activity))
        activity.refresh_from_db()
        self.assertFalse(activity.map_preview)


@override_settings(MEDIA_ROOT='/tmp/vsrala_test_media_map_preview')
class MapPreviewUploadAndFeedTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = Profile.objects.create_user(email='feedmap@example.com', password='testpass123')
        self.client.login(email='feedmap@example.com', password='testpass123')

    @patch('activities.map_preview._fetch_tile', side_effect=_fake_tile)
    def test_upload_gpx_sets_map_preview(self, _mock):
        content = (FIXTURES / 'sample.gpx').read_bytes()
        upload = SimpleUploadedFile('sample.gpx', content, content_type='application/gpx+xml')
        response = self.client.post(reverse('webinterface:activity_upload'), {
            'track_file': upload,
            'title': 'Outdoor',
        })
        self.assertEqual(response.status_code, 302)
        activity = Activity.objects.get(profile=self.user)
        self.assertTrue(activity.map_preview.name)

    @patch('activities.map_preview._fetch_tile', side_effect=_fake_tile)
    def test_feed_shows_lazy_preview_not_leaflet(self, _mock):
        activity = Activity.objects.create(
            profile=self.user,
            title='С превью',
            distance=10,
            started_at=datetime.now(),
            track_points=[[55.75, 37.6], [55.76, 37.61]],
        )
        apply_map_preview(activity)
        activity.refresh_from_db()

        response = self.client.get(reverse('webinterface:feed'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'loading="lazy"')
        self.assertContains(response, activity.map_preview.url)
        self.assertNotContains(response, 'data-track-map')
        self.assertNotContains(response, 'data-points=')

    def test_indoor_apply_parsed_track_no_preview(self):
        activity = Activity(profile=self.user, started_at=datetime.now())
        parsed = ParsedTrack(
            started_at=datetime.now(),
            duration=timedelta(minutes=30),
            duration_active=timedelta(minutes=30),
            distance_km=0,
            points=[],
            streams={'time': [0, 10], 'hr': [120, 130], 'power': []},
        )
        activity.apply_parsed_track(parsed)
        activity.save()
        self.assertFalse(apply_map_preview(activity))
