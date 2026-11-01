from __future__ import annotations

import gzip
import zipfile
from datetime import timedelta
from decimal import Decimal
from io import BytesIO
from pathlib import Path
from unittest.mock import MagicMock, patch

from django.test import Client, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone as dj_timezone

from activities.models import Activity, ActivityType
from integrations.dedup import (
    SOURCE_GARMIN,
    SOURCE_INTERVALS,
    find_duplicate_activity,
    merge_activity,
)
from integrations.garmin_client import GarminApiError, GarminClient, exchange_api_key_for_token
from integrations.garmin_sync import (
    connect_profile as garmin_connect_profile,
    disconnect_profile as garmin_disconnect_profile,
    import_remote_activity as garmin_import_remote_activity,
    map_garmin_power_zones,
    sync_power_zones,
)
from integrations.intervals_client import IntervalsApiError, IntervalsClient, _maybe_gunzip
from integrations.models import GarminConnection, IntervalsConnection
from integrations.sync import (
    EXTERNAL_SOURCE,
    connect_profile,
    disconnect_profile,
    import_remote_activity,
    sync_connection,
)
from integrations.tasks import sync_all_connections, sync_all_garmin_connections
from profiles.models import Profile

FIXTURES = Path(__file__).resolve().parent.parent / 'activities' / 'tests' / 'fixtures'


def _fit_zip(fit_bytes: bytes, name: str = 'activity.fit') -> bytes:
    buf = BytesIO()
    with zipfile.ZipFile(buf, 'w') as zf:
        zf.writestr(name, fit_bytes)
    return buf.getvalue()


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

    @patch('activities.zone_timeline.apply_zone_timeline')
    @patch('activities.map_preview.apply_map_preview')
    def test_import_remote_activity_creates_activity(self, _map, _zone):
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

    @patch('activities.zone_timeline.apply_zone_timeline')
    @patch('activities.map_preview.apply_map_preview')
    def test_import_idempotent_by_external_id(self, _map, _zone):
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

    @patch('activities.zone_timeline.apply_zone_timeline')
    @patch('activities.map_preview.apply_map_preview')
    @patch('integrations.sync.IntervalsClient')
    def test_sync_connection_initial(self, mock_client_cls, _map, _zone):
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


class GarminClientTest(TestCase):
    @patch('integrations.garmin_client.requests.Session.post')
    def test_exchange_api_key_for_token(self, mock_post):
        # Minimal JWT with exp far in the future
        import base64
        import json

        payload = base64.urlsafe_b64encode(
            json.dumps({'exp': 9999999999}).encode()
        ).decode().rstrip('=')
        token = f'aaa.{payload}.bbb'
        response = MagicMock()
        response.ok = True
        response.text = token
        mock_post.return_value = response

        access, expires = exchange_api_key_for_token('my-key')
        self.assertEqual(access, token)
        self.assertIsNotNone(expires)
        mock_post.assert_called_once()
        _, kwargs = mock_post.call_args
        self.assertIn('ApiKey my-key', kwargs['headers']['Authorization'])

    @patch('integrations.garmin_client.requests.Session.request')
    def test_search_activities(self, mock_request):
        response = MagicMock()
        response.ok = True
        response.content = b'[{}]'
        response.json.return_value = [{'activityId': 1}]
        mock_request.return_value = response

        client = GarminClient('bearer')
        items = client.search_activities(start_date='2024-01-01', end_date='2024-02-01')
        self.assertEqual(items[0]['activityId'], 1)


class DedupMergeTest(TestCase):
    def setUp(self):
        self.profile = Profile.objects.create_user(email='dedup@example.com', password='x')
        self.started = dj_timezone.now()

    def test_find_duplicate_by_time_distance(self):
        Activity.objects.create(
            profile=self.profile,
            title='A',
            started_at=self.started,
            distance=Decimal('42.00'),
            duration=timedelta(hours=1, minutes=30),
            external_source=SOURCE_INTERVALS,
            external_id='i1',
        )
        match = find_duplicate_activity(
            self.profile,
            started_at=self.started + timedelta(seconds=30),
            distance=Decimal('42.50'),
            duration=timedelta(hours=1, minutes=32),
        )
        self.assertIsNotNone(match)
        self.assertEqual(match.external_id, 'i1')

    def test_merge_garmin_priority(self):
        existing = Activity.objects.create(
            profile=self.profile,
            title='Intervals title',
            started_at=self.started,
            distance=Decimal('10.00'),
            duration=timedelta(hours=1),
            avg_hr=140,
            external_source=SOURCE_INTERVALS,
            external_id='i9',
            external_refs={SOURCE_INTERVALS: 'i9'},
        )
        merge_activity(
            existing,
            source=SOURCE_GARMIN,
            external_id='g9',
            field_values={
                'title': 'Garmin title',
                'calories': 500,
                'device_name': 'Edge 840',
                'avg_hr': 150,
            },
            prefer_incoming=True,
        )
        existing.refresh_from_db()
        self.assertEqual(existing.external_source, SOURCE_GARMIN)
        self.assertEqual(existing.external_id, 'g9')
        self.assertEqual(existing.external_refs[SOURCE_GARMIN], 'g9')
        self.assertEqual(existing.external_refs[SOURCE_INTERVALS], 'i9')
        self.assertEqual(existing.title, 'Garmin title')
        self.assertEqual(existing.calories, 500)
        self.assertEqual(existing.avg_hr, 150)
        self.assertEqual(existing.device_name, 'Edge 840')

    def test_merge_intervals_fills_empty_only(self):
        existing = Activity.objects.create(
            profile=self.profile,
            title='Garmin',
            started_at=self.started,
            distance=Decimal('10.00'),
            duration=timedelta(hours=1),
            avg_hr=150,
            calories=400,
            external_source=SOURCE_GARMIN,
            external_id='g1',
            external_refs={SOURCE_GARMIN: 'g1'},
        )
        merge_activity(
            existing,
            source=SOURCE_INTERVALS,
            external_id='i1',
            field_values={
                'title': 'Intervals overwrite attempt',
                'avg_hr': 999,
                'description': 'from intervals',
                'calories': 999,
            },
            prefer_incoming=False,
        )
        existing.refresh_from_db()
        self.assertEqual(existing.external_source, SOURCE_GARMIN)
        self.assertEqual(existing.title, 'Garmin')
        self.assertEqual(existing.avg_hr, 150)
        self.assertEqual(existing.calories, 400)
        self.assertEqual(existing.description, 'from intervals')
        self.assertEqual(existing.external_refs[SOURCE_INTERVALS], 'i1')


class GarminSyncServiceTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        ActivityType.objects.create(name='Шоссейный велосипед')

    def setUp(self):
        self.profile = Profile.objects.create_user(email='g@example.com', password='testpass123')
        self.connection = GarminConnection.objects.create(
            profile=self.profile,
            api_key='valid-key',
            access_token='token',
            token_expires_at=dj_timezone.now() + timedelta(days=1),
            is_active=True,
        )
        self.fit_bytes = (FIXTURES / 'sample.fit').read_bytes()
        self.zip_bytes = _fit_zip(self.fit_bytes)

    @patch('integrations.garmin_sync.verify_api_key')
    def test_connect_profile(self, mock_verify):
        mock_verify.return_value = {
            'settings': {'id': 'user-1', 'displayName': 'Rider'},
            'access_token': 'tok',
            'token_expires_at': dj_timezone.now() + timedelta(hours=2),
        }
        other = Profile.objects.create_user(email='g2@example.com', password='x')
        conn = garmin_connect_profile(other, 'new-key')
        self.assertTrue(conn.is_active)
        self.assertEqual(conn.api_key, 'new-key')
        self.assertEqual(conn.access_token, 'tok')

    def test_disconnect_profile(self):
        garmin_disconnect_profile(self.profile)
        self.connection.refresh_from_db()
        self.assertFalse(self.connection.is_active)
        self.assertEqual(self.connection.api_key, '')
        self.assertEqual(self.connection.access_token, '')

    @patch('activities.zone_timeline.apply_zone_timeline')
    @patch('activities.map_preview.apply_map_preview')
    def test_import_creates_garmin_activity(self, _map, _zone):
        client = MagicMock()
        client.get_activity.return_value = {
            'summaryDTO': {
                'activityName': 'Garmin Ride',
                'calories': 650,
                'trainingEffect': 3.2,
                'anaerobicTrainingEffect': 1.1,
                'deviceName': 'Edge 840',
                'averageTemperature': 18.5,
                'vO2MaxValue': 52.0,
                'activityType': {'typeKey': 'cycling'},
            },
            'metadataDTO': {'deviceName': 'Edge 840'},
        }
        client.download_activity.return_value = self.zip_bytes
        remote = {'activityId': 555, 'activityName': 'Garmin Ride'}

        activity = garmin_import_remote_activity(self.connection, client, remote)
        self.assertIsNotNone(activity)
        self.assertTrue(getattr(activity, '_was_created', False))
        self.assertEqual(activity.external_source, SOURCE_GARMIN)
        self.assertEqual(activity.external_id, '555')
        self.assertEqual(activity.calories, 650)
        self.assertEqual(activity.device_name, 'Edge 840')
        self.assertEqual(float(activity.aerobic_training_effect), 3.2)

    @patch('activities.zone_timeline.apply_zone_timeline')
    @patch('activities.map_preview.apply_map_preview')
    def test_cross_source_dedup_intervals_then_garmin(self, _map, _zone):
        intervals_conn = IntervalsConnection.objects.create(
            profile=self.profile,
            api_key='ik',
            athlete_id='1',
            is_active=True,
        )
        intervals_client = MagicMock()
        intervals_client.download_original_file.return_value = self.fit_bytes
        first = import_remote_activity(
            intervals_conn,
            intervals_client,
            {'id': 'i777', 'name': 'From Intervals', 'type': 'Ride', 'file_type': 'fit'},
        )
        self.assertIsNotNone(first)
        self.assertEqual(Activity.objects.filter(profile=self.profile).count(), 1)

        garmin_client = MagicMock()
        garmin_client.get_activity.return_value = {
            'summaryDTO': {
                'calories': 700,
                'trainingEffect': 2.5,
                'deviceName': 'Fenix',
                'activityType': {'typeKey': 'cycling'},
            },
        }
        garmin_client.download_activity.return_value = self.zip_bytes
        second = garmin_import_remote_activity(
            self.connection,
            garmin_client,
            {'activityId': 888, 'activityName': 'From Garmin'},
        )
        self.assertIsNotNone(second)
        self.assertFalse(getattr(second, '_was_created', True))
        self.assertEqual(Activity.objects.filter(profile=self.profile).count(), 1)
        second.refresh_from_db()
        self.assertEqual(second.external_source, SOURCE_GARMIN)
        self.assertEqual(second.external_id, '888')
        self.assertEqual(second.external_refs[SOURCE_INTERVALS], 'i777')
        self.assertEqual(second.external_refs[SOURCE_GARMIN], '888')
        self.assertEqual(second.calories, 700)

    @patch('activities.zone_timeline.apply_zone_timeline')
    @patch('activities.map_preview.apply_map_preview')
    def test_cross_source_dedup_garmin_then_intervals(self, _map, _zone):
        garmin_client = MagicMock()
        garmin_client.get_activity.return_value = {
            'summaryDTO': {
                'calories': 500,
                'deviceName': 'Edge',
                'activityType': {'typeKey': 'cycling'},
            },
        }
        garmin_client.download_activity.return_value = self.zip_bytes
        first = garmin_import_remote_activity(
            self.connection,
            garmin_client,
            {'activityId': 111, 'activityName': 'Garmin first'},
        )
        self.assertTrue(getattr(first, '_was_created', False))

        intervals_conn = IntervalsConnection.objects.create(
            profile=self.profile,
            api_key='ik',
            athlete_id='1',
            is_active=True,
        )
        intervals_client = MagicMock()
        intervals_client.download_original_file.return_value = self.fit_bytes
        second = import_remote_activity(
            intervals_conn,
            intervals_client,
            {'id': 'i111', 'name': 'Intervals later', 'type': 'Ride', 'file_type': 'fit'},
        )
        self.assertFalse(getattr(second, '_was_created', True))
        self.assertEqual(Activity.objects.filter(profile=self.profile).count(), 1)
        second.refresh_from_db()
        self.assertEqual(second.external_source, SOURCE_GARMIN)
        self.assertEqual(second.external_refs[SOURCE_INTERVALS], 'i111')
        self.assertEqual(second.calories, 500)
        self.assertEqual(second.title, 'Garmin first')

    def test_map_garmin_power_zones(self):
        raw = [{
            'sport': 'cycling',
            'ftp': 250,
            'powerZones': [
                {'zoneLowBoundary': 0, 'zoneHighBoundary': 137, 'name': 'Z1'},
                {'zoneLowBoundary': 138, 'zoneHighBoundary': 187, 'name': 'Z2'},
                {'zoneLowBoundary': 188, 'zoneHighBoundary': 225, 'name': 'Z3'},
                {'zoneLowBoundary': 226, 'zoneHighBoundary': 262, 'name': 'Z4'},
                {'zoneLowBoundary': 263, 'zoneHighBoundary': 300, 'name': 'Z5'},
                {'zoneLowBoundary': 301, 'zoneHighBoundary': 375, 'name': 'Z6'},
                {'zoneLowBoundary': 376, 'zoneHighBoundary': None, 'name': 'Z7'},
            ],
        }]
        zones = map_garmin_power_zones(raw)
        self.assertIsNotNone(zones)
        self.assertEqual(len(zones), 7)
        self.assertEqual(zones[0]['min'], 0)
        self.assertIsNone(zones[6]['max'])

    @patch('integrations.garmin_sync._client_for_connection')
    def test_sync_power_zones(self, mock_client_factory):
        client = MagicMock()
        mock_client_factory.return_value = client
        client.get_power_zones.return_value = [{
            'sport': 'cycling',
            'ftp': 220,
            'powerZones': [
                {'zoneLowBoundary': 0, 'zoneHighBoundary': 120},
                {'zoneLowBoundary': 121, 'zoneHighBoundary': 165},
                {'zoneLowBoundary': 166, 'zoneHighBoundary': 198},
                {'zoneLowBoundary': 199, 'zoneHighBoundary': 231},
                {'zoneLowBoundary': 232, 'zoneHighBoundary': 264},
                {'zoneLowBoundary': 265, 'zoneHighBoundary': 330},
                {'zoneLowBoundary': 331, 'zoneHighBoundary': None},
            ],
        }]
        client.get_cycling_ftp.return_value = {'functionalThresholdPower': 220}

        result = sync_power_zones(self.connection)
        self.profile.refresh_from_db()
        self.assertEqual(len(self.profile.power_zones), 7)
        self.assertEqual(self.profile.ftp, 220)
        self.assertEqual(result['ftp'], 220)


@override_settings(CELERY_TASK_ALWAYS_EAGER=True)
class GarminSettingsViewTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = Profile.objects.create_user(email='garmin-me@example.com', password='testpass123')
        self.client.login(email='garmin-me@example.com', password='testpass123')
        self.url = reverse('webinterface:settings')

    def test_settings_shows_garmin_form(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Garmin')
        self.assertContains(response, 'Personal API Token')

    @patch('webinterface.views.sync_garmin_connection.delay')
    @patch('webinterface.views.garmin_sync_service.connect_profile')
    def test_garmin_connect_success(self, mock_connect, mock_delay):
        conn = GarminConnection(
            pk=7,
            profile=self.user,
            api_key='key',
            is_active=True,
        )
        mock_connect.return_value = conn
        response = self.client.post(self.url, {
            'action': 'garmin_connect',
            'api_key': 'garmin-secret',
        })
        self.assertRedirects(response, self.url)
        mock_connect.assert_called_once_with(self.user, 'garmin-secret')
        mock_delay.assert_called_once_with(7, initial=True)

    @patch('webinterface.views.garmin_sync_service.connect_profile')
    def test_garmin_connect_invalid(self, mock_connect):
        mock_connect.side_effect = GarminApiError('bad', status_code=401)
        response = self.client.post(self.url, {
            'action': 'garmin_connect',
            'api_key': 'bad',
        })
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Не удалось подключиться')

    def test_garmin_disconnect(self):
        GarminConnection.objects.create(
            profile=self.user,
            api_key='key',
            is_active=True,
        )
        response = self.client.post(self.url, {'action': 'garmin_disconnect'})
        self.assertRedirects(response, self.url)
        conn = GarminConnection.objects.get(profile=self.user)
        self.assertFalse(conn.is_active)

    @patch('webinterface.views.garmin_sync_service.sync_power_zones')
    def test_garmin_sync_power_zones_button(self, mock_sync):
        GarminConnection.objects.create(
            profile=self.user,
            api_key='key',
            is_active=True,
            initial_sync_done=True,
        )
        mock_sync.return_value = {'zones': [], 'ftp': 200}
        response = self.client.post(self.url, {'action': 'garmin_sync_power_zones'})
        self.assertRedirects(response, self.url)
        mock_sync.assert_called_once()

    @patch('integrations.tasks.sync_garmin_connection.delay')
    def test_sync_all_garmin_enqueues(self, mock_delay):
        conn = GarminConnection.objects.create(
            profile=self.user,
            api_key='key',
            is_active=True,
            initial_sync_done=True,
        )
        result = sync_all_garmin_connections()
        self.assertEqual(result['enqueued'], 1)
        mock_delay.assert_called_once_with(conn.pk, initial=False)


class ActivitySourceBadgeTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = Profile.objects.create_user(
            email='badge@example.com', password='testpass123', is_public=True,
        )
        self.client.login(email='badge@example.com', password='testpass123')

    def test_feed_shows_source_icon_for_garmin(self):
        Activity.objects.create(
            profile=self.user,
            title='Ride',
            started_at=dj_timezone.now(),
            distance=Decimal('10'),
            duration=timedelta(hours=1),
            external_source=SOURCE_GARMIN,
            external_id='1',
        )
        response = self.client.get(reverse('webinterface:feed'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'source-garmin.svg')

    def test_detail_shows_upload_icon_when_no_source(self):
        activity = Activity.objects.create(
            profile=self.user,
            title='Manual',
            started_at=dj_timezone.now(),
            distance=Decimal('5'),
            duration=timedelta(minutes=30),
        )
        response = self.client.get(reverse('webinterface:activity_detail', args=[activity.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'source-upload.svg')
