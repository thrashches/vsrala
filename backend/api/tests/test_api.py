from datetime import datetime, timezone

from django.test import TestCase
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient

from activities.models import Activity, ActivityType
from profiles.models import FollowRequest, Profile
from routes.models import Route


class ApiAuthTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = Profile.objects.create_user(
            email='api@example.com', password='secret123',
        )

    def test_swagger_docs_available(self):
        response = self.client.get('/api/docs/')
        self.assertEqual(response.status_code, 200)
        schema = self.client.get('/api/schema/')
        self.assertEqual(schema.status_code, 200)
        self.assertIn(b'/api/auth/token/', schema.content)

    def test_obtain_token_with_email(self):
        response = self.client.post('/api/auth/token/', {
            'email': 'api@example.com',
            'password': 'secret123',
        }, format='json')
        self.assertEqual(response.status_code, 200)
        self.assertIn('token', response.data)
        self.assertEqual(response.data['email'], 'api@example.com')

    def test_obtain_token_invalid(self):
        response = self.client.post('/api/auth/token/', {
            'email': 'api@example.com',
            'password': 'wrong',
        }, format='json')
        self.assertEqual(response.status_code, 400)

    def test_requires_auth(self):
        response = self.client.get('/api/activities/')
        self.assertEqual(response.status_code, 401)

    def test_logout_deletes_token(self):
        token = Token.objects.create(user=self.user)
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {token.key}')
        response = self.client.post('/api/auth/logout/')
        self.assertEqual(response.status_code, 204)
        self.assertFalse(Token.objects.filter(user=self.user).exists())


class ApiActivityTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = Profile.objects.create_user(
            email='owner@example.com', password='secret123',
        )
        self.other = Profile.objects.create_user(
            email='other@example.com', password='secret123', is_public=True,
        )
        self.token = Token.objects.create(user=self.user)
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.token.key}')
        self.activity = Activity.objects.create(
            profile=self.user,
            title='Ride',
            started_at=datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc),
            distance=10,
        )

    def test_list_feed(self):
        response = self.client.get('/api/activities/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['count'], 1)

    def test_list_mine(self):
        Activity.objects.create(
            profile=self.other,
            title='Other',
            started_at=datetime(2026, 1, 2, 12, 0, tzinfo=timezone.utc),
        )
        response = self.client.get('/api/activities/?scope=mine')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['count'], 1)
        self.assertEqual(response.data['results'][0]['title'], 'Ride')

    def test_detail_and_update(self):
        response = self.client.get(f'/api/activities/{self.activity.pk}/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['title'], 'Ride')

        response = self.client.patch(
            f'/api/activities/{self.activity.pk}/',
            {'title': 'Updated'},
            format='json',
        )
        self.assertEqual(response.status_code, 200)
        self.activity.refresh_from_db()
        self.assertEqual(self.activity.title, 'Updated')

    def test_delete(self):
        response = self.client.delete(f'/api/activities/{self.activity.pk}/')
        self.assertEqual(response.status_code, 204)
        self.assertFalse(Activity.objects.filter(pk=self.activity.pk).exists())

    def test_react(self):
        response = self.client.post(
            f'/api/activities/{self.activity.pk}/react/',
            {'emoji': '👍'},
            format='json',
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['mine'], '👍')

    def test_comment_create(self):
        response = self.client.post(
            f'/api/activities/{self.activity.pk}/comments/',
            {'text': 'Nice ride'},
            format='json',
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data['comment']['text'], 'Nice ride')


class ApiPeopleMeTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = Profile.objects.create_user(
            email='me@example.com', password='secret123', first_name='Me',
        )
        self.other = Profile.objects.create_user(
            email='them@example.com', password='secret123',
            first_name='Them', is_public=True,
        )
        self.token = Token.objects.create(user=self.user)
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.token.key}')

    def test_me_get_patch(self):
        response = self.client.get('/api/me/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['email'], 'me@example.com')

        response = self.client.patch('/api/me/', {'first_name': 'Updated'}, format='json')
        self.assertEqual(response.status_code, 200)
        self.user.refresh_from_db()
        self.assertEqual(self.user.first_name, 'Updated')

    def test_people_search(self):
        response = self.client.get('/api/people/search/', {'q': 'Them'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data['results']), 1)

    def test_follow_toggle(self):
        response = self.client.post(f'/api/people/{self.other.pk}/follow/')
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data['is_following'])

        response = self.client.post(f'/api/people/{self.other.pk}/follow/')
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.data['is_following'])

    def test_follow_request_accept(self):
        req = FollowRequest.objects.create(from_user=self.other, to_user=self.user)
        response = self.client.post(f'/api/people/requests/{req.pk}/accept/')
        self.assertEqual(response.status_code, 200)
        self.assertFalse(FollowRequest.objects.filter(pk=req.pk).exists())
        self.assertTrue(self.other.follows.filter(pk=self.user.pk).exists())

    def test_password_change(self):
        response = self.client.post('/api/me/password/', {
            'old_password': 'secret123',
            'new_password1': 'new-secret-456',
            'new_password2': 'new-secret-456',
        }, format='json')
        self.assertEqual(response.status_code, 200)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password('new-secret-456'))


class ApiRoutesLeadersTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = Profile.objects.create_user(
            email='routes@example.com', password='secret123',
        )
        self.token = Token.objects.create(user=self.user)
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.token.key}')
        self.route = Route.objects.create(
            profile=self.user,
            title='Loop',
            visibility=Route.Visibility.PRIVATE,
            track_points=[{'lat': 1.0, 'lon': 2.0}, {'lat': 1.1, 'lon': 2.1}],
            distance=5,
        )
        ActivityType.objects.get_or_create(name='Ride')

    def test_route_list_and_detail(self):
        response = self.client.get('/api/routes/?tab=mine')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['count'], 1)

        response = self.client.get(f'/api/routes/{self.route.pk}/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['title'], 'Loop')
        self.assertIn('track_points', response.data)

    def test_route_update_delete(self):
        response = self.client.patch(
            f'/api/routes/{self.route.pk}/',
            {'title': 'New Loop'},
            format='json',
        )
        self.assertEqual(response.status_code, 200)
        self.route.refresh_from_db()
        self.assertEqual(self.route.title, 'New Loop')

        response = self.client.delete(f'/api/routes/{self.route.pk}/')
        self.assertEqual(response.status_code, 204)

    def test_weekly_leaders(self):
        response = self.client.get('/api/leaders/weekly/')
        self.assertEqual(response.status_code, 200)
        self.assertIn('leaders', response.data)
