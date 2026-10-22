from __future__ import annotations

import logging
import zipfile
from datetime import datetime, timedelta, timezone as dt_timezone
from decimal import Decimal, InvalidOperation
from io import BytesIO
from typing import Any, Optional

from django.core.files.base import ContentFile
from django.db import IntegrityError
from django.utils import timezone as dj_timezone

from activities.models import Activity, ActivityType
from activities.parsers import TrackParseError, parse_track
from profiles.zones import POWER_ZONE_NAMES, normalize_zones

from .dedup import (
    SOURCE_GARMIN,
    find_activity_by_external_id,
    find_duplicate_activity,
    merge_activity,
)
from .garmin_client import (
    GarminApiError,
    GarminClient,
    TOKEN_REFRESH_WINDOW_SECONDS,
    exchange_api_key_for_token,
)
from .models import GarminConnection

logger = logging.getLogger(__name__)

EXTERNAL_SOURCE = SOURCE_GARMIN

# Map Garmin activityType typeKey → local ActivityType names.
TYPE_NAME_MAP = {
    'cycling': 'Шоссейный велосипед',
    'road_biking': 'Шоссейный велосипед',
    'virtual_ride': 'Шоссейный велосипед',
    'indoor_cycling': 'Шоссейный велосипед',
    'mountain_biking': 'Горный велосипед',
    'gravel_cycling': 'Кроссовый велосипед',
    'track_cycling': 'Трековый велосипед',
    'running': 'Бег',
    'treadmill_running': 'Бег',
    'trail_running': 'Бег',
    'swimming': 'Заплыв',
    'lap_swimming': 'Заплыв',
    'open_water_swimming': 'Заплыв',
}


def _client_for_connection(connection: GarminConnection) -> GarminClient:
    """Return client with a valid bearer token; refresh and persist if needed."""
    now = dj_timezone.now()
    needs_refresh = (
        not connection.access_token
        or not connection.token_expires_at
        or connection.token_expires_at <= now + timedelta(seconds=TOKEN_REFRESH_WINDOW_SECONDS)
    )
    if needs_refresh:
        token, expires_at = exchange_api_key_for_token(connection.api_key)
        connection.access_token = token
        connection.token_expires_at = expires_at
        connection.save(update_fields=['access_token', 'token_expires_at', 'updated_at'])
    return GarminClient(connection.access_token)


def verify_api_key(api_key: str) -> dict:
    """Validate API key by exchanging token and fetching profile settings."""
    token, expires_at = exchange_api_key_for_token(api_key)
    client = GarminClient(token)
    settings = client.get_user_profile_settings()
    return {'settings': settings, 'access_token': token, 'token_expires_at': expires_at}


def connect_profile(profile, api_key: str) -> GarminConnection:
    verified = verify_api_key(api_key)
    settings = verified['settings']
    user_id = str(
        settings.get('id')
        or settings.get('userData', {}).get('userId')
        or settings.get('displayName')
        or ''
    )

    connection, _ = GarminConnection.objects.update_or_create(
        profile=profile,
        defaults={
            'api_key': api_key.strip(),
            'garmin_user_id': user_id,
            'access_token': verified['access_token'],
            'token_expires_at': verified['token_expires_at'],
            'is_active': True,
            'initial_sync_done': False,
            'last_error': '',
        },
    )
    return connection


def disconnect_profile(profile) -> None:
    try:
        connection = profile.garmin_connection
    except GarminConnection.DoesNotExist:
        return
    connection.is_active = False
    connection.api_key = ''
    connection.access_token = ''
    connection.token_expires_at = None
    connection.last_error = ''
    connection.save(update_fields=[
        'is_active', 'api_key', 'access_token', 'token_expires_at', 'last_error', 'updated_at',
    ])


def sync_connection(connection: GarminConnection, *, initial: bool = False) -> int:
    """Fetch activities from Garmin and import/merge. Returns newly created count."""
    if not connection.is_active or not connection.api_key:
        return 0

    today = dj_timezone.localdate()
    if initial or not connection.initial_sync_done:
        oldest = today - timedelta(days=183)
        initial = True
    elif connection.last_synced_at:
        oldest = (connection.last_synced_at - timedelta(days=1)).date()
    else:
        oldest = today - timedelta(days=7)
    newest = today + timedelta(days=1)

    try:
        client = _client_for_connection(connection)
        remote_activities = _list_all_activities(
            client,
            start_date=oldest.isoformat(),
            end_date=newest.isoformat(),
        )
    except GarminApiError as exc:
        connection.last_error = str(exc)
        connection.save(update_fields=['last_error', 'updated_at'])
        raise

    created = 0
    for remote in remote_activities:
        activity_id = str(remote.get('activityId') or remote.get('activityIdStr') or '')
        if not activity_id:
            continue
        if find_activity_by_external_id(connection.profile, EXTERNAL_SOURCE, activity_id):
            continue
        try:
            activity = import_remote_activity(connection, client, remote)
        except Exception:
            logger.exception(
                'Garmin sync: failed to import %s for profile %s',
                activity_id,
                connection.profile_id,
            )
            continue
        if activity is not None and getattr(activity, '_was_created', False):
            created += 1

    connection.last_synced_at = dj_timezone.now()
    connection.last_error = ''
    update_fields = ['last_synced_at', 'last_error', 'updated_at']
    if initial:
        connection.initial_sync_done = True
        update_fields.append('initial_sync_done')
    connection.save(update_fields=update_fields)
    return created


def _list_all_activities(
    client: GarminClient,
    *,
    start_date: str,
    end_date: str,
    page_size: int = 100,
) -> list[dict]:
    results: list[dict] = []
    start = 0
    while True:
        batch = client.search_activities(
            start=start,
            limit=page_size,
            start_date=start_date,
            end_date=end_date,
        )
        if not batch:
            break
        results.extend(batch)
        if len(batch) < page_size:
            break
        start += page_size
    return results


def import_remote_activity(
    connection: GarminConnection,
    client: GarminClient,
    remote: dict,
) -> Optional[Activity]:
    activity_id = str(remote.get('activityId') or remote.get('activityIdStr') or '')
    if not activity_id:
        return None

    detail: dict[str, Any] = {}
    try:
        detail = client.get_activity(activity_id)
    except GarminApiError as exc:
        logger.warning('Garmin sync: detail failed for %s: %s', activity_id, exc)

    file_bytes, filename = _download_fit_from_zip(client, activity_id)
    parsed = None
    if file_bytes:
        try:
            parsed = parse_track(BytesIO(file_bytes), filename=filename)
        except TrackParseError as exc:
            logger.warning('Garmin sync: parse failed for %s: %s', activity_id, exc)

    summary = _activity_summary(remote, detail)
    garmin_extras = extract_garmin_fields(summary, detail)

    title = (summary.get('activityName') or remote.get('activityName') or '').strip() or None
    description = (summary.get('description') or '').strip() or None
    activity_type = resolve_activity_type(_type_key(summary, remote))

    if parsed is not None:
        started_at = parsed.started_at
        duration = parsed.duration
        distance = parsed.distance_km
    else:
        started_at = _parse_started_at(summary, remote)
        if started_at is None:
            logger.warning('Garmin sync: no start time for %s', activity_id)
            return None
        duration = timedelta(seconds=float(summary.get('duration') or remote.get('duration') or 0))
        distance = _distance_km(summary, remote)

    field_values: dict[str, Any] = {
        'title': title,
        'description': description,
        'activity_type': activity_type,
        'started_at': started_at,
        **garmin_extras,
    }
    if parsed is not None:
        # Build temp activity to apply parsed metrics
        temp = Activity(profile=connection.profile, started_at=started_at)
        temp.apply_parsed_track(parsed)
        for name in (
            'duration', 'duration_active', 'distance', 'avg_speed', 'avg_moving_speed',
            'max_speed', 'avg_hr', 'max_hr', 'avg_power', 'max_power', 'normalized_power',
            'tss', 'avg_cadence', 'max_cadence', 'elevation_gain', 'elevation_loss',
            'elevation_min', 'elevation_max', 'track_points', 'streams', 'is_indoor',
        ):
            field_values[name] = getattr(temp, name)
        if file_bytes:
            field_values['track_file'] = ContentFile(file_bytes, name=filename)
    else:
        field_values['duration'] = duration
        field_values['distance'] = distance

    existing = find_duplicate_activity(
        connection.profile,
        started_at=started_at,
        distance=field_values.get('distance') or distance,
        duration=field_values.get('duration') or duration,
    )
    if existing is not None:
        merge_activity(
            existing,
            source=EXTERNAL_SOURCE,
            external_id=activity_id,
            field_values=field_values,
            prefer_incoming=True,
        )
        existing._was_created = False  # type: ignore[attr-defined]
        if prefer_track_refresh(existing, field_values):
            from activities.map_preview import apply_map_preview
            from activities.zone_timeline import apply_zone_timeline
            apply_map_preview(existing)
            apply_zone_timeline(existing)
        return existing

    activity = Activity(
        profile=connection.profile,
        title=title,
        description=description,
        activity_type=activity_type,
        external_source=EXTERNAL_SOURCE,
        external_id=activity_id,
        external_refs={EXTERNAL_SOURCE: activity_id},
        started_at=started_at,
    )
    for key, value in field_values.items():
        if key in ('title', 'description', 'activity_type', 'started_at'):
            continue
        if value is not None and value != '':
            setattr(activity, key, value)

    if file_bytes and 'track_file' in field_values:
        activity.track_file = field_values['track_file']

    try:
        activity.save()
    except IntegrityError:
        logger.info('Garmin sync: duplicate %s skipped', activity_id)
        return None

    from activities.map_preview import apply_map_preview
    from activities.zone_timeline import apply_zone_timeline
    apply_map_preview(activity)
    apply_zone_timeline(activity)
    activity._was_created = True  # type: ignore[attr-defined]
    return activity


def prefer_track_refresh(existing: Activity, field_values: dict) -> bool:
    return bool(field_values.get('track_points') or field_values.get('streams'))


def extract_garmin_fields(summary: dict, detail: dict | None = None) -> dict[str, Any]:
    """Pull Garmin-only metrics from activity summary/detail JSON."""
    detail = detail or {}
    summary_dto = detail.get('summaryDTO') if isinstance(detail.get('summaryDTO'), dict) else {}
    metadata = detail.get('metadataDTO') if isinstance(detail.get('metadataDTO'), dict) else {}
    # Prefer nested summaryDTO, then top-level list item fields.
    src = {**summary, **summary_dto}

    result: dict[str, Any] = {}

    calories = src.get('calories')
    if calories is not None:
        try:
            result['calories'] = int(float(calories))
        except (TypeError, ValueError):
            pass

    te = src.get('trainingEffect') or src.get('aerobicTrainingEffect')
    if te is not None:
        dec = _to_decimal(te)
        if dec is not None:
            result['aerobic_training_effect'] = dec

    ate = src.get('anaerobicTrainingEffect')
    if ate is not None:
        dec = _to_decimal(ate)
        if dec is not None:
            result['anaerobic_training_effect'] = dec

    device = (
        src.get('deviceName')
        or metadata.get('deviceName')
        or (metadata.get('deviceMetaData') or {}).get('deviceName')
        or ''
    )
    if device:
        result['device_name'] = str(device)[:128]

    temp = src.get('averageTemperature') or src.get('avgTemperature')
    if temp is not None:
        dec = _to_decimal(temp)
        if dec is not None:
            result['avg_temperature'] = dec

    vo2 = src.get('vO2MaxValue') or src.get('vo2MaxValue') or src.get('vo2max')
    if vo2 is not None:
        dec = _to_decimal(vo2)
        if dec is not None:
            result['vo2max'] = dec

    return result


def _to_decimal(value) -> Optional[Decimal]:
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return None


def _activity_summary(remote: dict, detail: dict) -> dict:
    summary = detail.get('summaryDTO') if isinstance(detail.get('summaryDTO'), dict) else {}
    return {**remote, **summary}


def _type_key(summary: dict, remote: dict) -> Optional[str]:
    for blob in (summary, remote):
        at = blob.get('activityType')
        if isinstance(at, dict):
            key = at.get('typeKey') or at.get('typeId')
            if key is not None:
                return str(key)
        elif isinstance(at, str):
            return at
    return None


def resolve_activity_type(type_key: Optional[str]) -> Optional[ActivityType]:
    if not type_key:
        return None
    name = TYPE_NAME_MAP.get(type_key) or TYPE_NAME_MAP.get(type_key.lower())
    if not name:
        return None
    return ActivityType.objects.filter(name=name).first()


def _parse_started_at(summary: dict, remote: dict):
    from django.utils.dateparse import parse_datetime

    for key in ('startTimeLocal', 'startTimeGMT', 'beginTimestamp'):
        raw = summary.get(key) or remote.get(key)
        if raw is None:
            continue
        if isinstance(raw, (int, float)):
            # Garmin sometimes returns epoch ms
            ts = float(raw)
            if ts > 1e12:
                ts /= 1000.0
            return datetime.fromtimestamp(ts, tz=dt_timezone.utc)
        if isinstance(raw, str):
            dt = parse_datetime(raw.replace('Z', '+00:00'))
            if dt is not None:
                if dj_timezone.is_naive(dt):
                    dt = dj_timezone.make_aware(dt, dj_timezone.get_current_timezone())
                return dt
    return None


def _distance_km(summary: dict, remote: dict) -> Decimal:
    # Garmin distances are usually metres
    raw = summary.get('distance') or remote.get('distance') or 0
    try:
        metres = float(raw)
    except (TypeError, ValueError):
        return Decimal('0')
    if metres > 1000:  # likely metres
        return Decimal(str(round(metres / 1000.0, 2)))
    return Decimal(str(round(metres, 2)))


def _download_fit_from_zip(client: GarminClient, activity_id: str) -> tuple[Optional[bytes], str]:
    try:
        zip_bytes = client.download_activity(activity_id)
    except GarminApiError as exc:
        logger.warning('Garmin sync: download failed for %s: %s', activity_id, exc)
        return None, ''

    try:
        with zipfile.ZipFile(BytesIO(zip_bytes)) as zf:
            for name in zf.namelist():
                lower = name.lower()
                if lower.endswith('.fit'):
                    return zf.read(name), f'{activity_id}.fit'
            for name in zf.namelist():
                if name.lower().endswith('.gpx'):
                    return zf.read(name), f'{activity_id}.gpx'
    except zipfile.BadZipFile:
        # Sometimes API returns raw FIT
        if zip_bytes[:2] == b'\x0e\x10' or b'.FIT' in zip_bytes[:20].upper():
            return zip_bytes, f'{activity_id}.fit'
        logger.warning('Garmin sync: invalid zip for %s', activity_id)
        return None, ''
    return None, ''


def sync_power_zones(connection: GarminConnection) -> dict[str, Any]:
    """
    Pull cycling power zones (+ FTP if available) into the user profile.
    Returns {'zones': [...], 'ftp': int|None}.
    """
    if not connection.is_active or not connection.api_key:
        raise GarminApiError('Garmin не подключён')

    client = _client_for_connection(connection)
    raw_zones = client.get_power_zones()
    zones = map_garmin_power_zones(raw_zones)
    if not zones:
        raise GarminApiError('Не удалось разобрать зоны мощности Garmin')

    ftp = extract_ftp(client, raw_zones)
    profile = connection.profile
    profile.power_zones = zones
    update_fields = ['power_zones']
    if ftp:
        profile.ftp = ftp
        update_fields.append('ftp')
    profile.save(update_fields=update_fields)
    return {'zones': zones, 'ftp': ftp}


def map_garmin_power_zones(raw: Any) -> Optional[list[dict[str, Any]]]:
    """Convert Garmin powerZones payload to local 7-zone format."""
    sport_block = _pick_cycling_zone_block(raw)
    if not sport_block:
        return None

    zone_list = (
        sport_block.get('powerZones')
        or sport_block.get('zones')
        or sport_block.get('zoneList')
    )
    if not isinstance(zone_list, list) or not zone_list:
        # Flat list of zone dicts on the block itself
        if isinstance(sport_block, list):
            zone_list = sport_block
        else:
            return None

    parsed: list[dict[str, Any]] = []
    for i, item in enumerate(zone_list):
        if not isinstance(item, dict):
            continue
        lo = item.get('zoneLowBoundary')
        if lo is None:
            lo = item.get('min') or item.get('low') or item.get('startValue')
        hi = item.get('zoneHighBoundary')
        if hi is None:
            hi = item.get('max') or item.get('high') or item.get('endValue')
        try:
            lo_i = int(float(lo)) if lo is not None else (parsed[-1]['max'] + 1 if parsed and parsed[-1].get('max') is not None else 0)
        except (TypeError, ValueError):
            continue
        try:
            hi_i: Optional[int] = int(float(hi)) if hi is not None else None
        except (TypeError, ValueError):
            hi_i = None
        name = (item.get('name') or item.get('zoneName') or '')
        if not name and i < len(POWER_ZONE_NAMES):
            name = POWER_ZONE_NAMES[i]
        parsed.append({'name': name or f'Z{i + 1}', 'min': lo_i, 'max': hi_i})

    if not parsed:
        return None

    # Ensure last zone is open-ended
    if parsed[-1].get('max') is not None and len(parsed) >= 7:
        parsed[-1]['max'] = None

    if len(parsed) == 7:
        normalized = normalize_zones(parsed, names=POWER_ZONE_NAMES)
        return normalized or parsed

    # Pad or trim to 7 zones using Joe Friel names
    if len(parsed) < 7:
        last_max = parsed[-1].get('max')
        while len(parsed) < 7:
            idx = len(parsed)
            lo = (last_max + 1) if last_max is not None else parsed[-1]['min']
            parsed.append({
                'name': POWER_ZONE_NAMES[idx] if idx < len(POWER_ZONE_NAMES) else f'Z{idx + 1}',
                'min': lo,
                'max': None if idx == 6 else lo + 50,
            })
            last_max = parsed[-1]['max']
        parsed[-1]['max'] = None
    else:
        parsed = parsed[:7]
        parsed[-1]['max'] = None

    for i, z in enumerate(parsed):
        if i < len(POWER_ZONE_NAMES):
            z['name'] = POWER_ZONE_NAMES[i]
    return normalize_zones(parsed, names=POWER_ZONE_NAMES) or parsed


def _pick_cycling_zone_block(raw: Any) -> Optional[dict]:
    if raw is None:
        return None
    if isinstance(raw, dict) and (
        'powerZones' in raw or 'zones' in raw or 'zoneList' in raw
    ):
        return raw
    items = raw if isinstance(raw, list) else (raw.get('userPowerZones') or raw.get('powerZones') or [])
    if not isinstance(items, list):
        return None
    cycling_keys = {'cycling', 'road_biking', 'bike', 'CYCLING', 'Cycling'}
    for item in items:
        if not isinstance(item, dict):
            continue
        sport = (
            item.get('sport')
            or item.get('sportType')
            or (item.get('activityType') or {}).get('typeKey')
            or ''
        )
        if str(sport) in cycling_keys or 'cycl' in str(sport).lower():
            return item
    # Fallback: first block with zones
    for item in items:
        if isinstance(item, dict) and (
            item.get('powerZones') or item.get('zones') or item.get('zoneList')
        ):
            return item
    return items[0] if items and isinstance(items[0], dict) else None


def extract_ftp(client: GarminClient, raw_zones: Any = None) -> Optional[int]:
    # Try dedicated endpoint first
    try:
        data = client.get_cycling_ftp()
        ftp = _ftp_from_payload(data)
        if ftp:
            return ftp
    except GarminApiError:
        pass

    block = _pick_cycling_zone_block(raw_zones)
    if block:
        for key in ('ftp', 'functionalThresholdPower', 'FTP'):
            if block.get(key) is not None:
                try:
                    return int(float(block[key]))
                except (TypeError, ValueError):
                    pass
    return None


def _ftp_from_payload(data: Any) -> Optional[int]:
    if data is None:
        return None
    if isinstance(data, list) and data:
        data = data[0]
    if not isinstance(data, dict):
        return None
    for key in ('functionalThresholdPower', 'ftp', 'value', 'ftpValue'):
        if data.get(key) is not None:
            try:
                return int(float(data[key]))
            except (TypeError, ValueError):
                continue
    return None
