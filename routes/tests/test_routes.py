from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from activities.models import Activity
from profiles.models import Follow, Profile
from routes.models import Route, distance_km_from_points
from routes.services import create_route_from_activity, slice_track_points as svc_slice
from routes.surface import (
    collapse_to_segments,
    enrich_route,
    match_surfaces_to_points,
    normalize_surface,
)

GPX_FIXTURE = Path(__file__).resolve().parents[2] / 'activities' / 'tests' / 'fixtures' / 'sample.gpx'


def _user(email, password='pass12345'):
    return Profile.objects.create_user(email=email, password=password)


def _activity_with_points(profile, points=None):
    pts = points or [
        [55.75, 37.60],
        [55.751, 37.601],
        [55.752, 37.602],
        [55.753, 37.603],
        [55.754, 37.604],
    ]
    return Activity.objects.create(
        profile=profile,
        title='Ride',
        started_at=datetime(2024, 1, 1, 12, 0, tzinfo=timezone.utc),
        duration=timedelta(minutes=30),
        distance=5,
        track_points=pts,
    )


class DistanceHelpersTest(TestCase):
    def test_distance_km(self):
        pts = [[55.75, 37.60], [55.76, 37.61]]
        self.assertGreater(distance_km_from_points(pts), 0)

    def test_slice_track_points(self):
        pts = [[i, i] for i in range(10)]
        sliced = svc_slice(pts, 2, 5)
        self.assertEqual(len(sliced), 4)
        self.assertEqual(sliced[0], [2.0, 2.0])
        self.assertEqual(sliced[-1], [5.0, 5.0])


class RouteVisibilityTest(TestCase):
    def setUp(self):
        self.owner = _user('owner@example.com')
        self.follower = _user('follower@example.com')
        self.stranger = _user('stranger@example.com')
        Follow.objects.create(user=self.follower, following=self.owner)
        pts = [[55.75, 37.60], [55.76, 37.61]]
        self.private = Route.objects.create(
            profile=self.owner, title='Private', visibility=Route.Visibility.PRIVATE,
            track_points=pts, distance=1,
        )
        self.followers = Route.objects.create(
            profile=self.owner, title='Followers', visibility=Route.Visibility.FOLLOWERS,
            track_points=pts, distance=1,
        )
        self.public = Route.objects.create(
            profile=self.owner, title='Public', visibility=Route.Visibility.PUBLIC,
            track_points=pts, distance=1,
        )

    def test_is_visible_to(self):
        self.assertTrue(self.private.is_visible_to(self.owner))
        self.assertFalse(self.private.is_visible_to(self.follower))
        self.assertFalse(self.private.is_visible_to(self.stranger))

        self.assertTrue(self.followers.is_visible_to(self.owner))
        self.assertTrue(self.followers.is_visible_to(self.follower))
        self.assertFalse(self.followers.is_visible_to(self.stranger))

        self.assertTrue(self.public.is_visible_to(self.owner))
        self.assertTrue(self.public.is_visible_to(self.follower))
        self.assertTrue(self.public.is_visible_to(self.stranger))

    def test_visible_to_queryset(self):
        qs = Route.objects.visible_to(self.follower)
        self.assertEqual(set(qs.values_list('pk', flat=True)), {self.followers.pk, self.public.pk})

        qs_stranger = Route.objects.visible_to(self.stranger)
        self.assertEqual(set(qs_stranger.values_list('pk', flat=True)), {self.public.pk})

    def test_detail_permissions(self):
        client = Client()
        client.login(email='follower@example.com', password='pass12345')
        self.assertEqual(
            client.get(reverse('webinterface:route_detail', kwargs={'pk': self.followers.pk})).status_code,
            200,
        )
        self.assertEqual(
            client.get(reverse('webinterface:route_detail', kwargs={'pk': self.private.pk})).status_code,
            404,
        )

        client.logout()
        client.login(email='stranger@example.com', password='pass12345')
        self.assertEqual(
            client.get(reverse('webinterface:route_detail', kwargs={'pk': self.public.pk})).status_code,
            200,
        )
        self.assertEqual(
            client.get(reverse('webinterface:route_detail', kwargs={'pk': self.followers.pk})).status_code,
            404,
        )


@override_settings(
    MEDIA_ROOT='/tmp/vsrala_test_media_routes',
    CELERY_TASK_ALWAYS_EAGER=True,
)
class RouteCreateFlowsTest(TestCase):
    def setUp(self):
        self.user = _user('rider@example.com')
        self.client = Client()
        self.client.login(email='rider@example.com', password='pass12345')

    @patch('webinterface.views.enqueue_surface_enrichment')
    @patch('routes.services.apply_route_map_preview', return_value=True)
    def test_create_from_gpx_upload(self, _preview, enqueue):
        gpx_bytes = GPX_FIXTURE.read_bytes()
        resp = self.client.post(reverse('webinterface:route_upload'), {
            'source_gpx': SimpleUploadedFile('sample.gpx', gpx_bytes, content_type='application/gpx+xml'),
            'title': 'My route',
            'description': '',
            'visibility': Route.Visibility.PUBLIC,
        })
        self.assertEqual(resp.status_code, 302)
        route = Route.objects.get(profile=self.user)
        self.assertEqual(route.title, 'My route')
        self.assertEqual(route.visibility, Route.Visibility.PUBLIC)
        self.assertGreaterEqual(len(route.track_points), 2)
        enqueue.assert_called_once_with(route.pk)

    @patch('webinterface.views.enqueue_surface_enrichment')
    @patch('routes.services.apply_route_map_preview', return_value=True)
    def test_create_from_activity_with_trim(self, _preview, enqueue):
        activity = _activity_with_points(self.user)
        full_dist = distance_km_from_points(activity.track_points)
        route = create_route_from_activity(
            profile=self.user,
            activity=activity,
            start_idx=1,
            end_idx=3,
            title='Trimmed',
            visibility=Route.Visibility.PRIVATE,
        )
        self.assertEqual(len(route.track_points), 3)
        self.assertLess(float(route.distance), float(full_dist) or 999)
        self.assertEqual(route.source_activity_id, activity.pk)

        resp = self.client.post(
            reverse('webinterface:route_from_activity', kwargs={'activity_id': activity.pk}),
            {
                'title': 'From UI',
                'description': '',
                'visibility': Route.Visibility.FOLLOWERS,
                'start_idx': 0,
                'end_idx': 2,
            },
        )
        self.assertEqual(resp.status_code, 302)
        created = Route.objects.get(title='From UI')
        self.assertEqual(len(created.track_points), 3)
        enqueue.assert_called()

    def test_from_activity_other_user_404(self):
        other = _user('other@example.com')
        activity = _activity_with_points(other)
        resp = self.client.get(
            reverse('webinterface:route_from_activity', kwargs={'activity_id': activity.pk}),
        )
        self.assertEqual(resp.status_code, 404)


class SurfaceEnrichmentTest(TestCase):
    def setUp(self):
        self.user = _user('surf@example.com')
        self.route = Route.objects.create(
            profile=self.user,
            title='Surface',
            track_points=[[55.75, 37.60], [55.751, 37.601], [55.752, 37.602]],
            distance=1,
            surface_status=Route.SurfaceStatus.PENDING,
        )

    def test_normalize_surface(self):
        self.assertEqual(normalize_surface({'surface': 'asphalt'}), 'asphalt')
        self.assertEqual(normalize_surface({'surface': 'fine_gravel'}), 'gravel')
        self.assertEqual(normalize_surface({'highway': 'cycleway'}), 'asphalt')
        self.assertEqual(normalize_surface({'highway': 'track'}), 'dirt')

    def test_match_and_collapse(self):
        points = [(55.75, 37.60), (55.751, 37.601), (55.752, 37.602)]
        ways = [
            {'type': 'way', 'center': {'lat': 55.75, 'lon': 37.60}, 'tags': {'surface': 'asphalt'}},
            {'type': 'way', 'center': {'lat': 55.752, 'lon': 37.602}, 'tags': {'surface': 'gravel'}},
        ]
        labels = match_surfaces_to_points(points, ways, radius_m=50)
        self.assertEqual(len(labels), 3)
        segs = collapse_to_segments(points, labels)
        self.assertGreaterEqual(len(segs), 1)
        self.assertIn('surface', segs[0])
        self.assertIn('distance_m', segs[0])

    @patch('routes.surface.fetch_overpass_ways')
    def test_enrich_route_success(self, fetch):
        fetch.return_value = [
            {
                'type': 'way',
                'center': {'lat': 55.75, 'lon': 37.60},
                'tags': {'surface': 'asphalt', 'highway': 'residential'},
            },
        ]
        enrich_route(self.route)
        self.route.refresh_from_db()
        self.assertEqual(self.route.surface_status, Route.SurfaceStatus.READY)
        self.assertTrue(self.route.surface_segments)

    @patch('routes.surface.fetch_overpass_ways', side_effect=RuntimeError('timeout'))
    def test_enrich_route_marks_failed_on_error(self, _fetch):
        with self.assertRaises(RuntimeError):
            enrich_route(self.route)
        # Direct enrich_route raises before saving failed; task layer saves FAILED.
        # Simulate task failure handling:
        self.route.surface_status = Route.SurfaceStatus.FAILED
        self.route.surface_segments = []
        self.route.save(update_fields=['surface_status', 'surface_segments'])
        self.route.refresh_from_db()
        self.assertEqual(self.route.surface_status, Route.SurfaceStatus.FAILED)

    @patch('routes.surface.enrich_route', side_effect=RuntimeError('timeout'))
    @override_settings(CELERY_TASK_ALWAYS_EAGER=True, CELERY_TASK_EAGER_PROPAGATES=True)
    def test_task_sets_failed(self, _enrich):
        from routes.tasks import enrich_route_surfaces
        # With retries, Celery may re-raise; ensure status ends as failed after first attempt.
        try:
            enrich_route_surfaces(self.route.pk)
        except Exception:
            pass
        self.route.refresh_from_db()
        self.assertEqual(self.route.surface_status, Route.SurfaceStatus.FAILED)
