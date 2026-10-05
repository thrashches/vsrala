from __future__ import annotations

import logging

from celery import shared_task
from django.contrib.auth import get_user_model

from .intervals_client import IntervalsApiError
from .models import IntervalsConnection
from . import sync as sync_service

logger = logging.getLogger(__name__)
Profile = get_user_model()


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


@shared_task(bind=True, max_retries=2, default_retry_delay=120)
def sync_connection(self, connection_id: int, initial: bool = False) -> dict:
    try:
        connection = IntervalsConnection.objects.select_related('profile').get(pk=connection_id)
    except IntervalsConnection.DoesNotExist:
        return {'ok': False, 'error': 'not_found'}

    if not connection.is_active:
        return {'ok': False, 'error': 'inactive'}

    try:
        created = sync_service.sync_connection(connection, initial=initial)
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
