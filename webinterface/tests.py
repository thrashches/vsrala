from datetime import datetime, timedelta
from decimal import Decimal

from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from activities.models import Activity, ActivityType
from profiles.models import Follow, FollowRequest, Profile


class ProfileSettingsViewTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = Profile.objects.create_user(email='me@example.com', password='testpass123')
        self.client.login(email='me@example.com', password='testpass123')
        self.url = reverse('webinterface:settings')

    def test_settings_page_requires_login(self):
        self.client.logout()
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 302)
        self.assertIn('/login/', response.url)

    def test_settings_page_ok(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Настройки')
        self.assertContains(response, 'Intervals.icu')
        self.assertContains(response, 'Garmin')

    def test_save_profile_settings(self):
        response = self.client.post(self.url, {
            'action': 'profile',
            'first_name': 'Вася',
            'email': 'new@example.com',
            'telegram': '@rider',
            'instagram': 'rider_ig',
            'vk': 'rider_vk',
            'is_public': 'on',
        })
        self.assertRedirects(response, self.url)
        self.user.refresh_from_db()
        self.assertEqual(self.user.first_name, 'Вася')
        self.assertEqual(self.user.email, 'new@example.com')
        self.assertEqual(self.user.telegram, '@rider')
        self.assertEqual(self.user.instagram, 'rider_ig')
        self.assertEqual(self.user.vk, 'rider_vk')
        self.assertTrue(self.user.is_public)

    def test_close_profile(self):
        response = self.client.post(self.url, {
            'action': 'profile',
            'first_name': '',
            'email': 'me@example.com',
            'telegram': '',
            'instagram': '',
            'vk': '',
        })
        self.assertRedirects(response, self.url)
        self.user.refresh_from_db()
        self.assertFalse(self.user.is_public)

    def test_duplicate_email_rejected(self):
        Profile.objects.create_user(email='taken@example.com', password='testpass123')
        response = self.client.post(self.url, {
            'action': 'profile',
            'first_name': '',
            'email': 'taken@example.com',
            'telegram': '',
            'instagram': '',
            'vk': '',
            'is_public': 'on',
        })
        self.assertEqual(response.status_code, 200)
        self.user.refresh_from_db()
        self.assertEqual(self.user.email, 'me@example.com')

    def test_change_password_success(self):
        response = self.client.post(self.url, {
            'action': 'password',
            'old_password': 'testpass123',
            'new_password1': 'NewPass456!',
            'new_password2': 'NewPass456!',
        })
        self.assertRedirects(response, self.url)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password('NewPass456!'))
        # Session stays authenticated after password change
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)

    def test_change_password_wrong_current(self):
        response = self.client.post(self.url, {
            'action': 'password',
            'old_password': 'wrong',
            'new_password1': 'NewPass456!',
            'new_password2': 'NewPass456!',
        })
        self.assertEqual(response.status_code, 200)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password('testpass123'))

    def test_delete_account(self):
        user_id = self.user.pk
        response = self.client.post(self.url, {
            'action': 'delete',
            'password': 'testpass123',
        })
        self.assertRedirects(response, reverse('webinterface:login'))
        self.assertFalse(Profile.objects.filter(pk=user_id).exists())
        # Logged out
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 302)

    def test_delete_account_wrong_password(self):
        response = self.client.post(self.url, {
            'action': 'delete',
            'password': 'wrong',
        })
        self.assertEqual(response.status_code, 200)
        self.assertTrue(Profile.objects.filter(pk=self.user.pk).exists())


class PrivacyFeedTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = Profile.objects.create_user(email='me@example.com', password='testpass123')
        self.friend = Profile.objects.create_user(
            email='friend@example.com', password='testpass123', is_public=False,
        )
        self.stranger_open = Profile.objects.create_user(
            email='open@example.com', password='testpass123', is_public=True,
        )
        self.stranger_closed = Profile.objects.create_user(
            email='closed@example.com', password='testpass123', is_public=False,
        )
        Follow.objects.create(user=self.user, following=self.friend)

        self.friend_activity = Activity.objects.create(
            profile=self.friend,
            title='Закрытая друга',
            distance=20,
            started_at=datetime.now(),
            track_points=[[55.75, 37.6], [55.76, 37.61]],
        )
        self.open_activity = Activity.objects.create(
            profile=self.stranger_open,
            title='Открытая чужая',
            distance=15,
            started_at=datetime.now(),
            track_points=[[55.75, 37.6], [55.76, 37.61]],
        )
        self.closed_stranger_activity = Activity.objects.create(
            profile=self.stranger_closed,
            title='Закрытая чужая',
            distance=25,
            started_at=datetime.now(),
            track_points=[[55.75, 37.6], [55.76, 37.61]],
        )
        Activity.objects.create(
            profile=self.user,
            title='Моя',
            distance=10,
            started_at=datetime.now(),
            track_points=[[55.75, 37.6], [55.76, 37.61]],
        )
        self.client.login(email='me@example.com', password='testpass123')

    def test_feed_visibility(self):
        response = self.client.get(reverse('webinterface:feed'))
        titles = [a.title for a in response.context['activities']]
        self.assertIn('Моя', titles)
        self.assertIn('Закрытая друга', titles)  # followed → visible
        self.assertNotIn('Открытая чужая', titles)  # not followed → hidden even if public
        self.assertNotIn('Закрытая чужая', titles)  # not followed → hidden

    def test_closed_detail_ok_for_follower(self):
        url = reverse('webinterface:activity_detail', kwargs={'pk': self.friend_activity.pk})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

    def test_closed_detail_404_for_non_follower(self):
        url = reverse(
            'webinterface:activity_detail',
            kwargs={'pk': self.closed_stranger_activity.pk},
        )
        response = self.client.get(url)
        self.assertEqual(response.status_code, 404)

    def test_open_detail_ok_for_anyone(self):
        url = reverse('webinterface:activity_detail', kwargs={'pk': self.open_activity.pk})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

    def test_owner_sees_own_closed_activity(self):
        self.client.logout()
        self.client.login(email='friend@example.com', password='testpass123')
        response = self.client.get(reverse('webinterface:feed'))
        titles = [a.title for a in response.context['activities']]
        self.assertIn('Закрытая друга', titles)
        url = reverse('webinterface:activity_detail', kwargs={'pk': self.friend_activity.pk})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)


class PeopleSearchAndFollowTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = Profile.objects.create_user(
            email='me@example.com', password='testpass123', first_name='Я',
        )
        self.vasya = Profile.objects.create_user(
            email='vasya@example.com', password='testpass123', first_name='Вася',
        )
        self.petya = Profile.objects.create_user(
            email='petya@mail.test', password='testpass123', first_name='Петя', is_public=False,
        )
        self.client.login(email='me@example.com', password='testpass123')

    def test_search_page_ok(self):
        response = self.client.get(reverse('webinterface:people_search'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Люди')

    def test_search_api_empty_query(self):
        response = self.client.get(reverse('webinterface:people_search_api'), {'q': ''})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['results'], [])

    def test_search_api_by_name(self):
        response = self.client.get(reverse('webinterface:people_search_api'), {'q': 'Вас'})
        self.assertEqual(response.status_code, 200)
        results = response.json()['results']
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]['id'], self.vasya.pk)
        self.assertEqual(results[0]['display_name'], 'Вася')
        self.assertFalse(results[0]['is_following'])

    def test_search_api_by_email(self):
        response = self.client.get(reverse('webinterface:people_search_api'), {'q': 'petya@'})
        results = response.json()['results']
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]['id'], self.petya.pk)

    def test_search_api_excludes_self(self):
        response = self.client.get(reverse('webinterface:people_search_api'), {'q': 'me@'})
        ids = [r['id'] for r in response.json()['results']]
        self.assertNotIn(self.user.pk, ids)

    def test_search_api_is_following_flag(self):
        Follow.objects.create(user=self.user, following=self.vasya)
        response = self.client.get(reverse('webinterface:people_search_api'), {'q': 'Вася'})
        self.assertTrue(response.json()['results'][0]['is_following'])

    def test_follow_and_unfollow(self):
        url = reverse('webinterface:profile_follow', kwargs={'pk': self.vasya.pk})
        response = self.client.post(url, HTTP_ACCEPT='application/json')
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data['is_following'])
        self.assertFalse(data['request_pending'])
        self.assertTrue(Follow.objects.filter(user=self.user, following=self.vasya).exists())

        response = self.client.post(url, HTTP_ACCEPT='application/json')
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertFalse(data['is_following'])
        self.assertFalse(data['request_pending'])
        self.assertFalse(Follow.objects.filter(user=self.user, following=self.vasya).exists())

    def test_closed_profile_creates_request(self):
        url = reverse('webinterface:profile_follow', kwargs={'pk': self.petya.pk})
        response = self.client.post(url, HTTP_ACCEPT='application/json')
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertFalse(data['is_following'])
        self.assertTrue(data['request_pending'])
        self.assertFalse(Follow.objects.filter(user=self.user, following=self.petya).exists())
        self.assertTrue(
            FollowRequest.objects.filter(from_user=self.user, to_user=self.petya).exists()
        )

    def test_cancel_pending_request(self):
        url = reverse('webinterface:profile_follow', kwargs={'pk': self.petya.pk})
        self.client.post(url, HTTP_ACCEPT='application/json')
        response = self.client.post(url, HTTP_ACCEPT='application/json')
        data = response.json()
        self.assertFalse(data['is_following'])
        self.assertFalse(data['request_pending'])
        self.assertFalse(
            FollowRequest.objects.filter(from_user=self.user, to_user=self.petya).exists()
        )

    def test_follow_back_on_closed_profile(self):
        Follow.objects.create(user=self.petya, following=self.user)
        url = reverse('webinterface:profile_follow', kwargs={'pk': self.petya.pk})
        response = self.client.post(url, HTTP_ACCEPT='application/json')
        data = response.json()
        self.assertTrue(data['is_following'])
        self.assertFalse(data['request_pending'])
        self.assertTrue(Follow.objects.filter(user=self.user, following=self.petya).exists())
        self.assertFalse(
            FollowRequest.objects.filter(from_user=self.user, to_user=self.petya).exists()
        )

    def test_accept_follow_request(self):
        req = FollowRequest.objects.create(from_user=self.vasya, to_user=self.user)
        url = reverse(
            'webinterface:follow_request_action',
            kwargs={'pk': req.pk, 'action': 'accept'},
        )
        response = self.client.post(url)
        self.assertEqual(response.status_code, 302)
        self.assertTrue(Follow.objects.filter(user=self.vasya, following=self.user).exists())
        self.assertFalse(FollowRequest.objects.filter(pk=req.pk).exists())

    def test_reject_follow_request(self):
        req = FollowRequest.objects.create(from_user=self.vasya, to_user=self.user)
        url = reverse(
            'webinterface:follow_request_action',
            kwargs={'pk': req.pk, 'action': 'reject'},
        )
        response = self.client.post(url)
        self.assertEqual(response.status_code, 302)
        self.assertFalse(Follow.objects.filter(user=self.vasya, following=self.user).exists())
        self.assertFalse(FollowRequest.objects.filter(pk=req.pk).exists())

    def test_follow_requests_page_and_navbar_indicator(self):
        FollowRequest.objects.create(from_user=self.vasya, to_user=self.user)
        response = self.client.get(reverse('webinterface:follow_requests'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Запросы на подписку')
        self.assertContains(response, 'Вася')
        self.assertContains(response, 'Принять')
        self.assertEqual(response.context['pending_follow_requests_count'], 1)

        feed = self.client.get(reverse('webinterface:feed'))
        self.assertEqual(feed.status_code, 200)
        self.assertContains(feed, 'aria-label="Запросы"')
        self.assertContains(feed, 'новых запросов')

    def test_cannot_follow_self(self):
        url = reverse('webinterface:profile_follow', kwargs={'pk': self.user.pk})
        response = self.client.post(url, HTTP_ACCEPT='application/json')
        self.assertEqual(response.status_code, 400)
        self.assertFalse(Follow.objects.filter(user=self.user, following=self.user).exists())

    def test_follow_unique(self):
        Follow.objects.create(user=self.user, following=self.vasya)
        with self.assertRaises(Exception):
            Follow.objects.create(user=self.user, following=self.vasya)

    def test_profile_page(self):
        response = self.client.get(
            reverse('webinterface:profile_detail', kwargs={'pk': self.vasya.pk})
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Вася')
        self.assertContains(response, 'Подписаться')

    def test_closed_profile_activities_hidden_until_follow(self):
        Activity.objects.create(
            profile=self.petya,
            title='Секрет Петя',
            distance=12,
            started_at=datetime.now(),
        )
        url = reverse('webinterface:profile_detail', kwargs={'pk': self.petya.pk})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'Секрет Петя')
        self.assertContains(response, 'Закрытый профиль')
        self.assertIsNone(response.context['year_stats'])
        self.assertNotContains(response, 'Статистика')

        Follow.objects.create(user=self.user, following=self.petya)
        response = self.client.get(url)
        self.assertContains(response, 'Секрет Петя')
        self.assertIsNotNone(response.context['year_stats'])
        self.assertContains(response, 'Статистика')

    def test_profile_year_stats_card(self):
        tz = timezone.get_current_timezone()
        Activity.objects.create(
            profile=self.vasya,
            title='Этот год',
            distance=Decimal('25.00'),
            duration=timedelta(hours=1),
            elevation_gain=Decimal('50.0'),
            started_at=timezone.now(),
        )
        Activity.objects.create(
            profile=self.vasya,
            title='Прошлый год',
            distance=Decimal('80.00'),
            duration=timedelta(hours=3),
            elevation_gain=Decimal('200.0'),
            started_at=timezone.make_aware(datetime(timezone.now().year - 1, 6, 1, 10, 0), tz),
        )
        response = self.client.get(
            reverse('webinterface:profile_detail', kwargs={'pk': self.vasya.pk})
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Статистика')
        year_stats = response.context['year_stats']
        self.assertIsNotNone(year_stats)
        current_year = timezone.now().astimezone(tz).year
        self.assertEqual(year_stats['selected_year'], current_year)
        self.assertIn(current_year, year_stats['years'])
        self.assertIn(current_year - 1, year_stats['years'])
        self.assertEqual(year_stats['by_year'][current_year]['distance'], '25')
        self.assertEqual(year_stats['by_year'][current_year - 1]['distance'], '80')
        self.assertContains(response, str(current_year - 1))

    def test_following_and_followers_lists(self):
        Follow.objects.create(user=self.user, following=self.vasya)
        Follow.objects.create(user=self.petya, following=self.user)

        following = self.client.get(
            reverse('webinterface:profile_following', kwargs={'pk': self.user.pk})
        )
        self.assertEqual(following.status_code, 200)
        self.assertContains(following, 'Вася')
        self.assertContains(following, 'Подписки')

        followers = self.client.get(
            reverse('webinterface:profile_followers', kwargs={'pk': self.user.pk})
        )
        self.assertEqual(followers.status_code, 200)
        self.assertContains(followers, 'Петя')
        self.assertContains(followers, 'Подписчики')


class WeeklyLeadersApiTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = Profile.objects.create_user(
            email='me@example.com', password='testpass123', first_name='Я',
        )
        self.friend = Profile.objects.create_user(
            email='friend@example.com', password='testpass123', first_name='Друг',
        )
        Follow.objects.create(user=self.user, following=self.friend)
        self.ride = ActivityType.objects.create(name='Шоссейный велосипед')
        Activity.objects.create(
            profile=self.friend,
            title='Заезд',
            activity_type=self.ride,
            distance=Decimal('50.00'),
            duration=timedelta(hours=2),
            started_at=timezone.now(),
        )
        self.url = reverse('webinterface:weekly_leaders_api')

    def test_requires_login(self):
        self.client.logout()
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 302)

    def test_json_ok(self):
        self.client.login(email='me@example.com', password='testpass123')
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['metric'], 'distance')
        self.assertEqual(data['week'], 'current')
        self.assertIn('week_label', data)
        self.assertTrue(any(r['profile_id'] == self.friend.pk for r in data['leaders']))

    def test_feed_includes_leaders_card(self):
        self.client.login(email='me@example.com', password='testpass123')
        response = self.client.get(reverse('webinterface:feed'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Лидеры недели')
        self.assertIn('weekly_leaders', response.context)
        self.assertContains(response, 'Друг')

    def test_invalid_metric(self):
        self.client.login(email='me@example.com', password='testpass123')
        response = self.client.get(self.url, {'metric': 'power'})
        self.assertEqual(response.status_code, 400)
