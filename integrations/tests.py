from __future__ import annotations

import gzip
from pathlib import Path
from unittest.mock import MagicMock, patch

from django.test import Client, TestCase, override_settings
from django.urls import reverse

from activities.models import Activity, ActivityType
from integrations.intervals_client import IntervalsApiError, IntervalsClient, _maybe_gunzip
from integrations.models import IntervalsConnection
from integrations.sync import (
    EXTERNAL_SOURCE,
    connect_profile,
    disconnect_profile,
    import_remote_activity,
    sync_connection,
)
from integrations.tasks import sync_all_connections
from profiles.models import Profile

FIXTURES = Path(__file__).resolve().parent.parent / 'activities' / 'tests' / 'fixtures'


class MaybeGunzipTest(TestCase):
    def test_plain_bytes_passthrough(self):
        self.assertEqual(_maybe_gunzip(b'fitdata'), b'fitdata')

    def test_gzip_decompress(self):
        payload = gzip.compress(b'hello-fit')
        self.assertEqual(_maybe_gunzip(payload), b'hello-fit')


class IntervalsClientTest(TestCase):
    def setUp(self):
        self.client_api = IntervalsClient('test-key')

    @patch('integrations.intervals_client.requests.Session.request')
    def test_get_athlete_ok(self, mock_request):
        response = MagicMock()
        response.ok = True
        response.json.return_value = {'id': '2049151', 'name': 'Test'}
        mock_request.return_value = response

        athlete = self.client_api.get_athlete()
        self.assertEqual(athlete['id'], '2049151')
        mock_request.assert_called_once()
        args, kwargs = mock_request.call_args
        self.assertEqual(args[0], 'GET')
        self.assertIn('/athlete/0', args[1])

    @patch('integrations.intervals_client.requests.Session.request')
    def test_get_athlete_unauthorized(self, mock_request):
        response = MagicMock()
        response.ok = False
        response.status_code = 401
        response.text = 'Unauthorized'
        response.reason = 'Unauthorized'
        mock_request.return_value = response

        with self.assertRaises(IntervalsApiError) as ctx:
            self.client_api.get_athlete()
        self.assertEqual(ctx.exception.status_code, 401)

    @patch('integrations.intervals_client.requests.Session.request')
    def test_list_activities(self, mock_request):
        response = MagicMock()
        response.ok = True
        response.json.return_value = [{'id': 'i1', 'type': 'Ride'}]
        mock_request.return_value = response

        items = self.client_api.list_activities('2024-01-01', '2024-06-01')
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]['id'], 'i1')

    @patch('integrations.intervals_client.requests.Session.request')
    def test_download_original_file_gunzip(self, mock_request):
        raw = b'FITFILE'
        response = MagicMock()
        response.ok = True
        response.content = gzip.compress(raw)
        mock_request.return_value = response

        data = self.client_api.download_original_file('i55751783')
        self.assertEqual(data, raw)


class SyncServiceTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        ActivityType.objects.create(name='Шоссейный велосипед')
        ActivityType.objects.create(name='Бег')

    def setUp(self):
        self.profile = Profile.objects.create_user(email='rider@example.com', password='testpass123')
        self.connection = IntervalsConnection.objects.create(
            profile=self.profile,
            api_key='valid-key',
            athlete_id='123',
            is_active=True,
        )
        self.fit_bytes = (FIXTURES / 'sample.fit').read_bytes()

    @patch('integrations.sync.verify_api_key')
    def test_connect_profile(self, mock_verify):
        mock_verify.return_value = {'id': 999}
        other = Profile.objects.create_user(email='other@example.com', password='testpass123')
        conn = connect_profile(other, 'new-key')
        self.assertTrue(conn.is_active)
        self.assertEqual(conn.athlete_id, '999')
        self.assertEqual(conn.api_key, 'new-key')
        self.assertFalse(conn.initial_sync_done)

    def test_disconnect_profile(self):
        disconnect_profile(self.profile)
        self.connection.refresh_from_db()
        self.assertFalse(self.connection.is_active)
        self.assertEqual(self.connection.api_key, '')

    def test_import_remote_activity_creates_activity(self):
        client = MagicMock()
        client.download_original_file.return_value = self.fit_bytes
        remote = {
            'id': 'i100',
            'name': 'Morning Ride',
            'type': 'Ride',
            'file_type': 'fit',
            'description': 'test',
        }
        activity = import_remote_activity(self.connection, client, remote)
        self.assertIsNotNone(activity)
        self.assertEqual(activity.external_source, EXTERNAL_SOURCE)
        self.assertEqual(activity.external_id, 'i100')
        self.assertEqual(activity.title, 'Morning Ride')
        self.assertEqual(activity.activity_type.name, 'Шоссейный велосипед')
        self.assertTrue(activity.track_points)

    def test_import_idempotent_by_external_id(self):
        client = MagicMock()
        client.download_original_file.return_value = self.fit_bytes
        remote = {'id': 'i200', 'name': 'Ride', 'type': 'Ride', 'file_type': 'fit'}
        first = import_remote_activity(self.connection, client, remote)
        self.assertIsNotNone(first)
        self.assertEqual(Activity.objects.filter(external_id='i200').count(), 1)

        with patch('integrations.sync.IntervalsClient') as mock_client_cls:
            mock_client = MagicMock()
            mock_client_cls.return_value = mock_client
            mock_client.list_activities.return_value = [remote]
            mock_client.download_original_file.return_value = self.fit_bytes
            created = sync_connection(self.connection, initial=False)

        self.assertEqual(created, 0)
        self.assertEqual(Activity.objects.filter(external_id='i200').count(), 1)

    @patch('integrations.sync.IntervalsClient')
    def test_sync_connection_initial(self, mock_client_cls):
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
        mock_client.list_activities.return_value = [
            {'id': 'i300', 'name': 'Ride', 'type': 'Ride', 'file_type': 'fit'},
        ]
        mock_client.download_original_file.return_value = self.fit_bytes

        created = sync_connection(self.connection, initial=True)
        self.assertEqual(created, 1)
        self.connection.refresh_from_db()
        self.assertTrue(self.connection.initial_sync_done)
        self.assertIsNotNone(self.connection.last_synced_at)
        self.assertEqual(Activity.objects.filter(external_id='i300').count(), 1)

        # Second run should not create duplicates
        created_again = sync_connection(self.connection, initial=False)
        self.assertEqual(created_again, 0)
        self.assertEqual(Activity.objects.filter(external_id='i300').count(), 1)

    @patch('integrations.tasks.sync_connection.delay')
    def test_sync_all_connections_enqueues_ready(self, mock_delay):
        self.connection.initial_sync_done = True
        self.connection.save(update_fields=['initial_sync_done'])
        pending = IntervalsConnection.objects.create(
            profile=Profile.objects.create_user(email='pending@example.com', password='x'),
            api_key='k',
            is_active=True,
            initial_sync_done=False,
        )
        result = sync_all_connections()
        self.assertEqual(result['enqueued'], 1)
        mock_delay.assert_called_once_with(self.connection.pk, initial=False)
        self.assertTrue(pending.pk)  # still exists, just not enqueued


@override_settings(CELERY_TASK_ALWAYS_EAGER=True)
class IntervalsSettingsViewTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = Profile.objects.create_user(email='me@example.com', password='testpass123')
        self.client.login(email='me@example.com', password='testpass123')
        self.url = reverse('webinterface:settings')

    def test_settings_shows_intervals_form(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Intervals.icu')
        self.assertContains(response, 'API-ключ')
        self.assertContains(response, 'Подключить')

    @patch('webinterface.views.sync_connection.delay')
    @patch('webinterface.views.connect_profile')
    def test_connect_success(self, mock_connect, mock_delay):
        conn = IntervalsConnection(
            pk=1,
            profile=self.user,
            api_key='key',
            athlete_id='42',
            is_active=True,
        )
        mock_connect.return_value = conn

        response = self.client.post(self.url, {
            'action': 'intervals_connect',
            'api_key': 'my-secret-key',
        })
        self.assertRedirects(response, self.url)
        mock_connect.assert_called_once_with(self.user, 'my-secret-key')
        mock_delay.assert_called_once_with(1, initial=True)

    @patch('webinterface.views.connect_profile')
    def test_connect_invalid_key(self, mock_connect):
        mock_connect.side_effect = IntervalsApiError('bad key', status_code=401)
        response = self.client.post(self.url, {
            'action': 'intervals_connect',
            'api_key': 'bad',
        })
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Не удалось подключиться')
        self.assertFalse(
            IntervalsConnection.objects.filter(profile=self.user, is_active=True).exists()
        )

    def test_disconnect(self):
        IntervalsConnection.objects.create(
            profile=self.user,
            api_key='key',
            athlete_id='1',
            is_active=True,
        )
        response = self.client.post(self.url, {'action': 'intervals_disconnect'})
        self.assertRedirects(response, self.url)
        conn = IntervalsConnection.objects.get(profile=self.user)
        self.assertFalse(conn.is_active)
        self.assertEqual(conn.api_key, '')
