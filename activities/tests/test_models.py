from datetime import datetime, timedelta
from decimal import Decimal
from pathlib import Path

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase
from django.urls import reverse

from activities.models import Activity, ActivityType
from activities.track import format_track_lap_length
from profiles.models import Follow, Profile

FIXTURES = Path(__file__).parent.parent.parent / 'activities' / 'tests' / 'fixtures'


class ActivityModelTest(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.profile = Profile.objects.create(email='test@mail.ru')
        activity_types = [
            ActivityType(name='Шоссейный велосипед'),
            ActivityType(name='Горный велосипед'),
            ActivityType(name='Трековый велосипед'),
            ActivityType(name='Кроссовый велосипед'),
            ActivityType(name='Бег'),
            ActivityType(name='Заплыв'),
        ]
        cls.activity_types = ActivityType.objects.bulk_create(activity_types)

    def test_activity_types_init(self):
        activity_types = ActivityType.objects.all()
        assert activity_types.count() == 6, 'Типы тренировок не созданы!'

    def test_create_activity_model(self):
        activity_type = ActivityType.objects.first()
        Activity.objects.create(
            profile=self.profile,
            duration=timedelta(hours=2),
            activity_type=activity_type,
            distance=50.05,
            started_at=datetime.now()
        )
        activities = Activity.objects.all()
        assert activities.count() == 1, 'Не удалось создать тренировку!'

    def test_duration_display_always_hms(self):
        activity = Activity(
            profile=self.profile,
            duration=timedelta(minutes=45, seconds=7),
            duration_active=timedelta(minutes=40, seconds=3),
            started_at=datetime.now(),
        )
        self.assertEqual(activity.duration_display, '00:45:07')
        self.assertEqual(activity.duration_active_display, '00:40:03')

    def test_apply_parsed_track_computes_tss_from_ftp(self):
        from activities.parsers.base import ParsedTrack

        self.profile.ftp = 250
        self.profile.save(update_fields=['ftp'])
        activity = Activity(profile=self.profile, started_at=datetime.now())
        parsed = ParsedTrack(
            started_at=datetime.now(),
            duration=timedelta(hours=1),
            duration_active=timedelta(hours=1),
            distance_km=30.0,
            avg_speed=30.0,
            avg_moving_speed=30.0,
            normalized_power=250,
            tss=None,
        )
        activity.apply_parsed_track(parsed)
        self.assertEqual(float(activity.tss), 100.0)
        self.assertEqual(activity.normalized_power, 250)

    def test_track_lap_length_display(self):
        self.assertEqual(format_track_lap_length(Decimal('250')), '250 м')
        self.assertEqual(format_track_lap_length(Decimal('333.33')), '333,33 м')
        activity = Activity(
            profile=self.profile,
            started_at=datetime.now(),
            is_track=True,
            track_lap_length_m=Decimal('250'),
        )
        self.assertEqual(activity.track_lap_length_display, '250 м')

    def test_save_clears_lap_length_when_not_track(self):
        activity = Activity.objects.create(
            profile=self.profile,
            started_at=datetime.now(),
            is_track=False,
            track_lap_length_m=Decimal('250'),
            distance=1,
            duration=timedelta(minutes=10),
        )
        activity.refresh_from_db()
        self.assertIsNone(activity.track_lap_length_m)


class ActivityUploadViewTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = Profile.objects.create_user(email='rider@example.com', password='testpass123')
        self.client.login(email='rider@example.com', password='testpass123')
        self.track_type = ActivityType.objects.create(name='Трековый велосипед')
        self.road_type = ActivityType.objects.create(name='Шоссейный велосипед')

    def test_upload_gpx(self):
        content = (FIXTURES / 'sample.gpx').read_bytes()
        upload = SimpleUploadedFile('sample.gpx', content, content_type='application/gpx+xml')
        response = self.client.post(reverse('webinterface:activity_upload'), {
            'track_file': upload,
            'title': 'Тестовый заезд',
        })
        self.assertEqual(Activity.objects.count(), 1)
        activity = Activity.objects.get()
        self.assertRedirects(response, reverse('webinterface:activity_detail', kwargs={'pk': activity.pk}))
        self.assertEqual(activity.title, 'Тестовый заезд')
        self.assertGreater(float(activity.distance), 0)
        self.assertTrue(activity.track_points)
        self.assertEqual(activity.profile, self.user)

    def test_upload_rejects_bad_extension(self):
        upload = SimpleUploadedFile('notes.txt', b'hello', content_type='text/plain')
        response = self.client.post(reverse('webinterface:activity_upload'), {
            'track_file': upload,
        })
        self.assertEqual(Activity.objects.count(), 0)
        self.assertEqual(response.status_code, 200)

    def test_upload_track_type_sets_is_track_with_default_length(self):
        self.user.trains_on_track = True
        self.user.default_track_lap_length_m = Decimal('250')
        self.user.save()
        content = (FIXTURES / 'sample.gpx').read_bytes()
        upload = SimpleUploadedFile('sample.gpx', content, content_type='application/gpx+xml')
        response = self.client.post(reverse('webinterface:activity_upload'), {
            'track_file': upload,
            'title': 'Трек',
            'activity_type': self.track_type.pk,
            'track_lap_length_m': '250',
        })
        self.assertEqual(response.status_code, 302)
        activity = Activity.objects.get()
        self.assertTrue(activity.is_track)
        self.assertEqual(float(activity.track_lap_length_m), 250.0)

    def test_upload_track_length_override(self):
        self.user.trains_on_track = True
        self.user.default_track_lap_length_m = Decimal('250')
        self.user.save()
        content = (FIXTURES / 'sample.gpx').read_bytes()
        upload = SimpleUploadedFile('sample.gpx', content, content_type='application/gpx+xml')
        response = self.client.post(reverse('webinterface:activity_upload'), {
            'track_file': upload,
            'is_track': 'on',
            'track_lap_length_m': '400',
        })
        self.assertEqual(response.status_code, 302)
        activity = Activity.objects.get()
        self.assertTrue(activity.is_track)
        self.assertEqual(float(activity.track_lap_length_m), 400.0)

    def test_upload_track_requires_lap_length(self):
        content = (FIXTURES / 'sample.gpx').read_bytes()
        upload = SimpleUploadedFile('sample.gpx', content, content_type='application/gpx+xml')
        response = self.client.post(reverse('webinterface:activity_upload'), {
            'track_file': upload,
            'activity_type': self.track_type.pk,
        })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Activity.objects.count(), 0)


class ActivityEditViewTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = Profile.objects.create_user(email='rider@example.com', password='testpass123')
        self.other = Profile.objects.create_user(email='other@example.com', password='testpass123')
        self.client.login(email='rider@example.com', password='testpass123')
        self.activity = Activity.objects.create(
            profile=self.user,
            title='Заезд',
            distance=10,
            started_at=datetime.now(),
            duration=timedelta(minutes=30),
            is_track=True,
            track_lap_length_m=Decimal('250'),
        )

    def test_owner_can_edit(self):
        url = reverse('webinterface:activity_edit', kwargs={'pk': self.activity.pk})
        response = self.client.post(url, {
            'title': 'Обновлено',
            'description': '',
            'is_track': 'on',
            'track_lap_length_m': '333.33',
        })
        self.assertRedirects(
            response,
            reverse('webinterface:activity_detail', kwargs={'pk': self.activity.pk}),
        )
        self.activity.refresh_from_db()
        self.assertEqual(self.activity.title, 'Обновлено')
        self.assertEqual(float(self.activity.track_lap_length_m), 333.33)

    def test_clear_track_flag_clears_length(self):
        url = reverse('webinterface:activity_edit', kwargs={'pk': self.activity.pk})
        response = self.client.post(url, {
            'title': 'Заезд',
            'description': '',
        })
        self.assertEqual(response.status_code, 302)
        self.activity.refresh_from_db()
        self.assertFalse(self.activity.is_track)
        self.assertIsNone(self.activity.track_lap_length_m)

    def test_non_owner_gets_404(self):
        self.client.login(email='other@example.com', password='testpass123')
        url = reverse('webinterface:activity_edit', kwargs={'pk': self.activity.pk})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 404)


class FeedViewTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = Profile.objects.create_user(email='me@example.com', password='testpass123')
        self.friend = Profile.objects.create_user(email='friend@example.com', password='testpass123')
        self.stranger = Profile.objects.create_user(email='stranger@example.com', password='testpass123')
        Follow.objects.create(user=self.user, following=self.friend)

        Activity.objects.create(
            profile=self.user,
            title='Моя',
            distance=10,
            started_at=datetime.now(),
            track_points=[[55.75, 37.6], [55.76, 37.61]],
        )
        Activity.objects.create(
            profile=self.friend,
            title='Друга',
            distance=20,
            started_at=datetime.now(),
            track_points=[[55.75, 37.6], [55.76, 37.61]],
        )
        Activity.objects.create(
            profile=self.stranger,
            title='Чужая',
            distance=30,
            started_at=datetime.now(),
        )
        self.client.login(email='me@example.com', password='testpass123')

    def test_feed_shows_own_and_following_only(self):
        response = self.client.get(reverse('webinterface:feed'))
        self.assertEqual(response.status_code, 200)
        titles = [a.title for a in response.context['activities']]
        self.assertIn('Моя', titles)
        self.assertIn('Друга', titles)
        self.assertNotIn('Чужая', titles)
