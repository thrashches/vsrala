from datetime import datetime, timedelta
from pathlib import Path

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase
from django.urls import reverse

from activities.models import Activity, ActivityType
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



class ActivityUploadViewTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = Profile.objects.create_user(email='rider@example.com', password='testpass123')
        self.client.login(email='rider@example.com', password='testpass123')

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
