from pathlib import Path

from django.core.files.base import ContentFile
from django.test import TestCase
from django.utils import timezone

from activities.activity_types import (
    ensure_activity_type,
    resolve_fit_sport,
    resolve_garmin_type,
    resolve_intervals_type,
)
from activities.models import Activity, ActivityType
from activities.parsers.fit import read_fit_sport
from activities.services import update_activity_types_from_fit
from activities.tasks import update_activity_types_from_fit_task
from profiles.models import Profile

FIXTURES = Path(__file__).parent / 'fixtures'


class ActivityTypesResolveTest(TestCase):
    def test_resolve_intervals_known(self):
        at = resolve_intervals_type('Ride')
        self.assertIsNotNone(at)
        self.assertEqual(at.name, 'Шоссейный велосипед')
        self.assertEqual(at.slug, 'road_cycling')

    def test_resolve_intervals_walk(self):
        at = resolve_intervals_type('Walk')
        self.assertEqual(at.name, 'Ходьба')
        self.assertEqual(at.slug, 'walking')

    def test_resolve_garmin_creates_if_missing(self):
        ActivityType.objects.filter(name='Бег').delete()
        self.assertFalse(ActivityType.objects.filter(name='Бег').exists())
        at = resolve_garmin_type('running')
        self.assertIsNotNone(at)
        self.assertEqual(at.name, 'Бег')
        self.assertEqual(at.slug, 'running')

    def test_resolve_fit_sport(self):
        at = resolve_fit_sport('cycling', 'road')
        self.assertEqual(at.name, 'Шоссейный велосипед')
        at_run = resolve_fit_sport('running')
        self.assertEqual(at_run.name, 'Бег')

    def test_ensure_unknown_name(self):
        at = ensure_activity_type('Кастомный спорт')
        self.assertEqual(at.name, 'Кастомный спорт')
        self.assertTrue(ActivityType.objects.filter(name='Кастомный спорт').exists())


class UpdateActivityTypesFromFitTest(TestCase):
    def setUp(self):
        self.profile = Profile.objects.create_user(email='fit@example.com', password='pass')
        self.run = ActivityType.objects.get(slug='running')

    def test_read_fit_sport_from_fixture(self):
        sport, sub = read_fit_sport(FIXTURES / 'sample.fit')
        self.assertEqual(sport, 'running')

    def test_update_from_fit_sets_type(self):
        activity = Activity.objects.create(
            profile=self.profile,
            title='Without type',
            started_at=timezone.now(),
            activity_type=None,
        )
        fit_bytes = (FIXTURES / 'sample.fit').read_bytes()
        activity.track_file.save('sample.fit', ContentFile(fit_bytes), save=True)

        result = update_activity_types_from_fit(Activity.objects.filter(pk=activity.pk))
        activity.refresh_from_db()
        self.assertEqual(result['updated'], 1)
        self.assertEqual(activity.activity_type_id, self.run.pk)

    def test_update_skips_gpx(self):
        activity = Activity.objects.create(
            profile=self.profile,
            title='GPX',
            started_at=timezone.now(),
        )
        gpx_bytes = (FIXTURES / 'sample.gpx').read_bytes()
        activity.track_file.save('sample.gpx', ContentFile(gpx_bytes), save=True)

        result = update_activity_types_from_fit(Activity.objects.filter(pk=activity.pk))
        self.assertEqual(result['updated'], 0)
        self.assertEqual(result['skipped'], 1)
        self.assertIn('не FIT', result['skip_reasons'])

    def test_celery_task_updates_type(self):
        activity = Activity.objects.create(
            profile=self.profile,
            title='Task',
            started_at=timezone.now(),
            activity_type=None,
        )
        fit_bytes = (FIXTURES / 'sample.fit').read_bytes()
        activity.track_file.save('sample.fit', ContentFile(fit_bytes), save=True)

        result = update_activity_types_from_fit_task([activity.pk])
        activity.refresh_from_db()
        self.assertTrue(result['ok'])
        self.assertEqual(result['updated'], 1)
        self.assertEqual(activity.activity_type_id, self.run.pk)
