from __future__ import annotations

import logging
from datetime import date, datetime, timedelta
from decimal import Decimal, InvalidOperation
from io import BytesIO
from typing import Optional

from django.core.files.base import ContentFile
from django.db import IntegrityError
from django.utils import timezone as dj_timezone
from django.utils.dateparse import parse_datetime

from activities.activity_types import INTERVALS_TYPE_MAP, resolve_intervals_type
from activities.models import Activity
from activities.parsers import TrackParseError, parse_track
from activities.tasks import enqueue_activity_enrichment

from .dedup import (
    SOURCE_INTERVALS,
    find_duplicate_activity,
    known_external_ids,
    link_external_id_only,
    merge_activity,
)
from .intervals_client import IntervalsApiError, IntervalsClient
from .models import IntervalsConnection

logger = logging.getLogger(__name__)

EXTERNAL_SOURCE = SOURCE_INTERVALS

# Backwards-compatible alias for tests/imports.
TYPE_NAME_MAP = INTERVALS_TYPE_MAP

# Cap FIT downloads per sync run to keep Celery RSS stable on small VPS.
IMPORT_LIMIT_PER_RUN = 8


def verify_api_key(api_key: str) -> dict:
    """Validate API key and return athlete payload. Raises IntervalsApiError."""
    client = IntervalsClient(api_key)
    return client.get_athlete()


def connect_profile(profile, api_key: str) -> IntervalsConnection:
    """
    Verify key, upsert IntervalsConnection as active, reset sync flags.
    Caller should enqueue initial sync after this.
    """
    athlete = verify_api_key(api_key)
    athlete_id = str(athlete.get('id') or '')

    connection, _ = IntervalsConnection.objects.update_or_create(
        profile=profile,
        defaults={
            'api_key': api_key.strip(),
            'athlete_id': athlete_id,
            'is_active': True,
            'initial_sync_done': False,
            'last_error': '',
        },
    )
    return connection


def disconnect_profile(profile) -> None:
    try:
        connection = profile.intervals_connection
    except IntervalsConnection.DoesNotExist:
        return
    connection.is_active = False
    connection.api_key = ''
    connection.last_error = ''
    connection.save(update_fields=['is_active', 'api_key', 'last_error', 'updated_at'])


def sync_connection(connection: IntervalsConnection, *, initial: bool = False) -> int:
    """
    Fetch activities from Intervals and import missing ones.
    Returns number of newly created Activity rows.
    """
    if not connection.is_active or not connection.api_key:
        return 0

    today = dj_timezone.localdate()
    if initial or not connection.initial_sync_done:
        oldest = date(today.year, 1, 1)
        initial = True
    elif connection.last_synced_at:
        oldest = (connection.last_synced_at - timedelta(days=1)).date()
    else:
        oldest = today - timedelta(days=7)

    newest = today + timedelta(days=1)
    client = IntervalsClient(connection.api_key, athlete_id=connection.athlete_id or '0')
    created = 0
    imported_or_linked = 0
    has_more = False

    try:
        remote_activities = client.list_activities(
            oldest=oldest.isoformat(),
            newest=newest.isoformat(),
        )
    except IntervalsApiError as exc:
        connection.last_error = str(exc)
        connection.save(update_fields=['last_error', 'updated_at'])
        raise

    known_ids = known_external_ids(connection.profile, EXTERNAL_SOURCE)

    for remote in remote_activities:
        activity_id = str(remote.get('id') or '')
        if not activity_id:
            continue
        if activity_id in known_ids:
            continue

        linked = try_link_without_download(connection, remote)
        if linked is not None:
            known_ids.add(activity_id)
            imported_or_linked += 1
            continue

        if imported_or_linked >= IMPORT_LIMIT_PER_RUN:
            has_more = True
            break

        try:
            activity = import_remote_activity(connection, client, remote)
        except Exception:
            logger.exception(
                'Intervals sync: failed to import %s for profile %s',
                activity_id,
                connection.profile_id,
            )
            continue
        if activity is None:
            continue

        known_ids.add(activity_id)
        imported_or_linked += 1
        if getattr(activity, '_was_created', False):
            created += 1

    if has_more:
        # Keep the date window; continue on next task without advancing last_synced_at.
        connection.last_error = ''
        connection.save(update_fields=['last_error', 'updated_at'])
        _enqueue_continue(connection.pk, initial=initial)
        return created

    connection.last_synced_at = dj_timezone.now()
    connection.last_error = ''
    update_fields = ['last_synced_at', 'last_error', 'updated_at']
    if initial:
        connection.initial_sync_done = True
        update_fields.append('initial_sync_done')
    connection.save(update_fields=update_fields)
    return created


def _enqueue_continue(connection_id: int, *, initial: bool) -> None:
    try:
        from .tasks import sync_connection as sync_connection_task

        sync_connection_task.delay(connection_id, initial=initial)
    except Exception:
        logger.exception('Intervals sync: failed to enqueue continuation for %s', connection_id)


def try_link_without_download(
    connection: IntervalsConnection,
    remote: dict,
) -> Optional[Activity]:
    """
    If a local activity already has a track and matches Intervals summary fields,
    only attach the Intervals external id — skip FIT download/parse.
    """
    activity_id = str(remote.get('id') or '')
    if not activity_id:
        return None

    started_at = _intervals_started_at(remote)
    if started_at is None:
        return None

    distance = _intervals_distance_km(remote)
    duration = _intervals_duration(remote)
    existing = find_duplicate_activity(
        connection.profile,
        started_at=started_at,
        distance=distance,
        duration=duration,
    )
    if existing is None:
        return None
    if not existing.track_points and not existing.track_file:
        return None

    link_external_id_only(existing, source=EXTERNAL_SOURCE, external_id=activity_id)
    existing._was_created = False  # type: ignore[attr-defined]
    return existing


def import_remote_activity(
    connection: IntervalsConnection,
    client: IntervalsClient,
    remote: dict,
) -> Optional[Activity]:
    activity_id = str(remote.get('id') or '')
    if not activity_id:
        return None

    file_bytes, filename = _download_track_bytes(client, remote)
    if not file_bytes:
        logger.warning('Intervals sync: no downloadable file for %s', activity_id)
        return None

    try:
        parsed = parse_track(BytesIO(file_bytes), filename=filename)
    except TrackParseError as exc:
        logger.warning('Intervals sync: parse failed for %s: %s', activity_id, exc)
        return None

    title = (remote.get('name') or '').strip() or None
    description = (remote.get('description') or '').strip() or None
    activity_type = resolve_activity_type(remote.get('type'))

    temp = Activity(
        profile=connection.profile,
        title=title,
        description=description,
        activity_type=activity_type,
        started_at=parsed.started_at,
    )
    temp.apply_parsed_track(parsed)

    field_values = {
        'title': title,
        'description': description,
        'activity_type': activity_type,
        'started_at': parsed.started_at,
        'duration': temp.duration,
        'duration_active': temp.duration_active,
        'distance': temp.distance,
        'avg_speed': temp.avg_speed,
        'avg_moving_speed': temp.avg_moving_speed,
        'max_speed': temp.max_speed,
        'avg_hr': temp.avg_hr,
        'max_hr': temp.max_hr,
        'avg_power': temp.avg_power,
        'max_power': temp.max_power,
        'normalized_power': temp.normalized_power,
        'tss': temp.tss,
        'avg_cadence': temp.avg_cadence,
        'max_cadence': temp.max_cadence,
        'elevation_gain': temp.elevation_gain,
        'elevation_loss': temp.elevation_loss,
        'elevation_min': temp.elevation_min,
        'elevation_max': temp.elevation_max,
        'track_points': temp.track_points,
        'streams': temp.streams,
        'is_indoor': temp.is_indoor,
        'track_file': ContentFile(file_bytes, name=filename),
    }

    existing = find_duplicate_activity(
        connection.profile,
        started_at=parsed.started_at,
        distance=temp.distance,
        duration=temp.duration,
    )
    if existing is not None:
        # Garmin wins on conflicts: only fill empty fields when merging Intervals in.
        prefer_incoming = existing.external_source != 'garmin' and 'garmin' not in (existing.external_refs or {})
        merge_activity(
            existing,
            source=EXTERNAL_SOURCE,
            external_id=activity_id,
            field_values=field_values,
            prefer_incoming=prefer_incoming,
        )
        existing._was_created = False  # type: ignore[attr-defined]
        if prefer_incoming or field_values.get('track_points') or field_values.get('streams'):
            enqueue_activity_enrichment(existing.pk)
        return existing

    activity = Activity(
        profile=connection.profile,
        title=title,
        description=description,
        activity_type=activity_type,
        external_source=EXTERNAL_SOURCE,
        external_id=activity_id,
        external_refs={EXTERNAL_SOURCE: activity_id},
        started_at=parsed.started_at,
    )
    activity.apply_parsed_track(parsed)
    activity.track_file = ContentFile(file_bytes, name=filename)

    try:
        activity.save()
    except IntegrityError:
        logger.info('Intervals sync: duplicate %s skipped', activity_id)
        return None

    enqueue_activity_enrichment(activity.pk)
    activity._was_created = True  # type: ignore[attr-defined]
    return activity


def resolve_activity_type(intervals_type: Optional[str]):
    return resolve_intervals_type(intervals_type)


def _intervals_started_at(remote: dict) -> Optional[datetime]:
    for key in ('start_date_local', 'start_date', 'started'):
        raw = remote.get(key)
        if not raw:
            continue
        if isinstance(raw, datetime):
            dt = raw
        else:
            text = str(raw).replace('Z', '+00:00')
            dt = parse_datetime(text)
            if dt is None and len(text) >= 10:
                try:
                    day = date.fromisoformat(text[:10])
                    dt = datetime(day.year, day.month, day.day)
                except ValueError:
                    continue
        if dt is None:
            continue
        if dj_timezone.is_naive(dt):
            dt = dj_timezone.make_aware(dt, dj_timezone.get_current_timezone())
        return dt
    return None


def _intervals_distance_km(remote: dict) -> Decimal:
    raw = remote.get('distance')
    if raw is None:
        raw = remote.get('icu_distance')
    try:
        value = Decimal(str(raw or 0))
    except (InvalidOperation, TypeError, ValueError):
        return Decimal('0')
    # Intervals usually reports metres for distance.
    if value > Decimal('1000'):
        return (value / Decimal('1000')).quantize(Decimal('0.01'))
    return value.quantize(Decimal('0.01')) if value else Decimal('0')


def _intervals_duration(remote: dict) -> timedelta:
    for key in ('moving_time', 'elapsed_time', 'icu_recording_time', 'duration'):
        raw = remote.get(key)
        if raw is None:
            continue
        try:
            seconds = float(raw)
        except (TypeError, ValueError):
            continue
        if seconds > 0:
            return timedelta(seconds=seconds)
    return timedelta(0)


def _download_track_bytes(
    client: IntervalsClient,
    remote: dict,
) -> tuple[Optional[bytes], str]:
    activity_id = str(remote['id'])
    file_type = (remote.get('file_type') or '').lower().lstrip('.')

    if file_type in ('fit', 'gpx'):
        try:
            payload = client.download_original_file(activity_id)
            return payload, f'{activity_id}.{file_type}'
        except IntervalsApiError as exc:
            # Non-network 404: don't bother with fit-file for non-fit originals later.
            if exc.status_code == 404 and file_type == 'fit':
                try:
                    payload = client.download_fit_file(activity_id)
                    return payload, f'{activity_id}.fit'
                except IntervalsApiError as fit_exc:
                    logger.warning('Intervals sync: download failed for %s: %s', activity_id, fit_exc)
                    return None, ''
            logger.warning(
                'Intervals sync: original file failed for %s (%s), trying fit-file',
                activity_id,
                exc,
            )

    try:
        payload = client.download_fit_file(activity_id)
        return payload, f'{activity_id}.fit'
    except IntervalsApiError as exc:
        if file_type not in ('fit', 'gpx'):
            # Last resort: try original anyway
            try:
                payload = client.download_original_file(activity_id)
                ext = file_type or 'bin'
                if ext in ('fit', 'gpx'):
                    return payload, f'{activity_id}.{ext}'
                # Unknown format — try as fit
                return payload, f'{activity_id}.fit'
            except IntervalsApiError:
                pass
        logger.warning('Intervals sync: download failed for %s: %s', activity_id, exc)
        return None, ''
