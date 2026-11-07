from __future__ import annotations

import logging

from celery import shared_task
from celery.exceptions import SoftTimeLimitExceeded
from django.contrib.auth import get_user_model

from .garmin_client import GarminApiError
from .intervals_client import IntervalsApiError
from .models import GarminConnection, IntervalsConnection
from . import garmin_sync as garmin_sync_service
from . import sync as sync_service

logger = logging.getLogger(__name__)
Profile = get_user_model()

# Soft limit leaves room to persist last_error before hard kill.
_SYNC_SOFT_TIME_LIMIT = 10 * 60
_SYNC_TIME_LIMIT = 11 * 60


@shared_task(bind=True, max_retries=2, default_retry_delay=60)
def verify_and_connect(self, profile_id: int, api_key: str) -> dict:
    """
    Verify API key asynchronously, activate connection, kick off initial sync.
    Used when connection verification should not block the request.
    """
    try:
        profile = Profile.objects.get(pk=profile_id)
    except Profile.DoesNotExist:
        return {'ok': False, 'error': 'profile_not_found'}

    try:
        connection = sync_service.connect_profile(profile, api_key)
    except IntervalsApiError as exc:
        IntervalsConnection.objects.update_or_create(
            profile=profile,
            defaults={
                'api_key': '',
                'is_active': False,
                'last_error': str(exc),
            },
        )
        return {'ok': False, 'error': str(exc)}

    sync_connection.delay(connection.pk, initial=True)
    return {'ok': True, 'connection_id': connection.pk, 'athlete_id': connection.athlete_id}


@shared_task(
    bind=True,
    max_retries=2,
    default_retry_delay=120,
    soft_time_limit=_SYNC_SOFT_TIME_LIMIT,
    time_limit=_SYNC_TIME_LIMIT,
)
def sync_connection(self, connection_id: int, initial: bool = False) -> dict:
    try:
        connection = IntervalsConnection.objects.select_related('profile').get(pk=connection_id)
    except IntervalsConnection.DoesNotExist:
        return {'ok': False, 'error': 'not_found'}

    if not connection.is_active:
        return {'ok': False, 'error': 'inactive'}

    try:
        created = sync_service.sync_connection(connection, initial=initial)
    except SoftTimeLimitExceeded as exc:
        connection.last_error = f'soft_time_limit connection_id={connection_id}'
        connection.save(update_fields=['last_error', 'updated_at'])
        logger.warning('Intervals sync soft time limit for %s', connection_id)
        return {'ok': False, 'error': str(exc)}
    except IntervalsApiError as exc:
        logger.warning('Intervals sync failed for %s: %s', connection_id, exc)
        try:
            raise self.retry(exc=exc)
        except self.MaxRetriesExceededError:
            return {'ok': False, 'error': str(exc)}
    except Exception as exc:
        connection.last_error = str(exc)
        connection.save(update_fields=['last_error', 'updated_at'])
        logger.exception('Intervals sync error for %s', connection_id)
        return {'ok': False, 'error': str(exc)}

    return {'ok': True, 'created': created}


@shared_task
def sync_all_connections() -> dict:
    qs = IntervalsConnection.objects.filter(is_active=True, initial_sync_done=True)
    count = 0
    for connection_id in qs.values_list('pk', flat=True):
        sync_connection.delay(connection_id, initial=False)
        count += 1
    return {'ok': True, 'enqueued': count}


@shared_task(
    bind=True,
    max_retries=2,
    default_retry_delay=120,
    soft_time_limit=_SYNC_SOFT_TIME_LIMIT,
    time_limit=_SYNC_TIME_LIMIT,
)
def sync_garmin_connection(self, connection_id: int, initial: bool = False) -> dict:
    try:
        connection = GarminConnection.objects.select_related('profile').get(pk=connection_id)
    except GarminConnection.DoesNotExist:
        return {'ok': False, 'error': 'not_found'}

    if not connection.is_active:
        return {'ok': False, 'error': 'inactive'}

    try:
        created = garmin_sync_service.sync_connection(connection, initial=initial)
    except SoftTimeLimitExceeded as exc:
        connection.last_error = f'soft_time_limit connection_id={connection_id}'
        connection.save(update_fields=['last_error', 'updated_at'])
        logger.warning('Garmin sync soft time limit for %s', connection_id)
        return {'ok': False, 'error': str(exc)}
    except GarminApiError as exc:
        logger.warning('Garmin sync failed for %s: %s', connection_id, exc)
        try:
            raise self.retry(exc=exc)
        except self.MaxRetriesExceededError:
            return {'ok': False, 'error': str(exc)}
    except Exception as exc:
        connection.last_error = str(exc)
        connection.save(update_fields=['last_error', 'updated_at'])
        logger.exception('Garmin sync error for %s', connection_id)
        return {'ok': False, 'error': str(exc)}

    return {'ok': True, 'created': created}


@shared_task
def sync_all_garmin_connections() -> dict:
    """Enqueue active Garmin connections, including stuck unfinished initial syncs."""
    qs = GarminConnection.objects.filter(is_active=True)
    count = 0
    for connection_id, initial_done in qs.values_list('pk', 'initial_sync_done'):
        sync_garmin_connection.delay(connection_id, initial=not initial_done)
        count += 1
    return {'ok': True, 'enqueued': count}


@shared_task(bind=True, max_retries=1, default_retry_delay=300, soft_time_limit=600, time_limit=660)
def sync_intervals_metrics(self, connection_id: int, initial: bool = False) -> dict:
    from .intervals_client import IntervalsClient
    from .metric_history import sync_intervals_metric_history

    try:
        connection = IntervalsConnection.objects.select_related('profile').get(pk=connection_id)
    except IntervalsConnection.DoesNotExist:
        return {'ok': False, 'error': 'not_found'}
    if not connection.is_active or not connection.api_key:
        return {'ok': False, 'error': 'inactive'}

    client = IntervalsClient(connection.api_key, athlete_id=connection.athlete_id or '0')
    try:
        counts = sync_intervals_metric_history(connection, client, initial=initial)
    except SoftTimeLimitExceeded as exc:
        logger.warning('Intervals metrics soft time limit for %s', connection_id)
        return {'ok': False, 'error': str(exc)}
    except Exception as exc:
        logger.exception('Intervals metrics sync failed for %s', connection_id)
        return {'ok': False, 'error': str(exc)}
    return {'ok': True, 'counts': counts}


@shared_task(bind=True, max_retries=1, default_retry_delay=300, soft_time_limit=600, time_limit=660)
def sync_garmin_metrics(self, connection_id: int, initial: bool = False) -> dict:
    from .metric_history import sync_garmin_metric_history

    try:
        connection = GarminConnection.objects.select_related('profile').get(pk=connection_id)
    except GarminConnection.DoesNotExist:
        return {'ok': False, 'error': 'not_found'}
    if not connection.is_active or not connection.api_key:
        return {'ok': False, 'error': 'inactive'}

    try:
        client = garmin_sync_service._client_for_connection(connection)
        counts = sync_garmin_metric_history(connection, client, initial=initial)
    except SoftTimeLimitExceeded as exc:
        logger.warning('Garmin metrics soft time limit for %s', connection_id)
        return {'ok': False, 'error': str(exc)}
    except GarminApiError as exc:
        logger.warning('Garmin metrics sync failed for %s: %s', connection_id, exc)
        return {'ok': False, 'error': str(exc)}
    except Exception as exc:
        logger.exception('Garmin metrics sync error for %s', connection_id)
        return {'ok': False, 'error': str(exc)}
    return {'ok': True, 'counts': counts}


@shared_task
def sync_all_metric_history() -> dict:
    """Daily metric backfill for connections that finished initial activity sync."""
    intervals_n = 0
    for connection_id in (
        IntervalsConnection.objects.filter(is_active=True, initial_sync_done=True)
        .values_list('pk', flat=True)
    ):
        sync_intervals_metrics.delay(connection_id, initial=False)
        intervals_n += 1

    garmin_n = 0
    for connection_id in (
        GarminConnection.objects.filter(is_active=True, initial_sync_done=True)
        .values_list('pk', flat=True)
    ):
        sync_garmin_metrics.delay(connection_id, initial=False)
        garmin_n += 1

    return {'ok': True, 'intervals': intervals_n, 'garmin': garmin_n}
