from __future__ import annotations

import logging
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation
from typing import Any, Iterable, Optional

from django.utils import timezone as dj_timezone

from profiles.metrics import upsert_metric_sample
from profiles.models import ProfileMetricSample

from .garmin_client import GarminApiError, GarminClient
from .intervals_client import IntervalsApiError, IntervalsClient
from .models import GarminConnection, IntervalsConnection

logger = logging.getLogger(__name__)

INITIAL_LOOKBACK_DAYS = 365 * 3
# Periodic metric sync lookback (activity sync is a separate beat task).
INCREMENTAL_LOOKBACK_DAYS = 7
CHUNK_DAYS = 90

# Process-local skip list for Personal API endpoints that return 404.
_UNSUPPORTED_GARMIN_METRICS: set[str] = set()


def _to_decimal(value) -> Optional[Decimal]:
    if value is None or value == '':
        return None
    try:
        dec = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return None
    return dec if dec.is_finite() else None


def _date_chunks(start: date, end: date, chunk_days: int = CHUNK_DAYS) -> Iterable[tuple[date, date]]:
    if start > end:
        return
    cursor = start
    delta = timedelta(days=chunk_days - 1)
    while cursor <= end:
        chunk_end = min(cursor + delta, end)
        yield cursor, chunk_end
        cursor = chunk_end + timedelta(days=1)


def _metric_window(*, initial: bool, last_synced_at) -> tuple[date, date]:
    today = dj_timezone.localdate()
    if initial:
        oldest = today - timedelta(days=INITIAL_LOOKBACK_DAYS)
    elif last_synced_at:
        oldest = (last_synced_at - timedelta(days=1)).date()
        # Cap lookback: do not go further than INCREMENTAL_LOOKBACK_DAYS.
        oldest = max(oldest, today - timedelta(days=INCREMENTAL_LOOKBACK_DAYS))
    else:
        oldest = today - timedelta(days=INCREMENTAL_LOOKBACK_DAYS)
    return oldest, today


def sync_garmin_metric_history(
    connection: GarminConnection,
    client: GarminClient,
    *,
    initial: bool = False,
) -> dict[str, int]:
    oldest, newest = _metric_window(initial=initial, last_synced_at=connection.last_synced_at)
    counts = {'weight': 0, 'ftp': 0, 'vo2max': 0}
    profile = connection.profile

    for start, end in _date_chunks(oldest, newest):
        counts['weight'] += _sync_garmin_weight(profile, client, start, end)
        counts['ftp'] += _sync_garmin_ftp_stats(profile, client, start, end)
        counts['vo2max'] += _sync_garmin_vo2max(profile, client, start, end)

    # Current FTP snapshot (dedicated endpoint is more reliable than stats).
    try:
        from .garmin_sync import extract_ftp

        ftp = extract_ftp(client)
        if ftp:
            sample = upsert_metric_sample(
                profile,
                metric=ProfileMetricSample.Metric.FTP,
                recorded_on=newest,
                value=ftp,
                source=ProfileMetricSample.Source.GARMIN,
                external_key='latest_ftp',
            )
            if sample:
                counts['ftp'] += 1
    except Exception:
        logger.exception('Garmin metric sync: latest FTP failed for %s', connection.pk)

    counts['vo2max'] += backfill_vo2max_from_activities(profile, oldest, newest)
    return counts


def sync_intervals_metric_history(
    connection: IntervalsConnection,
    client: IntervalsClient,
    *,
    initial: bool = False,
    remote_activities: Optional[list[dict]] = None,
) -> dict[str, int]:
    oldest, newest = _metric_window(initial=initial, last_synced_at=connection.last_synced_at)
    counts = {'weight': 0, 'ftp': 0, 'vo2max': 0}
    profile = connection.profile

    for start, end in _date_chunks(oldest, newest):
        try:
            wellness = client.list_wellness(start.isoformat(), end.isoformat())
        except IntervalsApiError as exc:
            logger.warning('Intervals wellness sync failed: %s', exc)
            wellness = []
        w, v = ingest_intervals_wellness(profile, wellness)
        counts['weight'] += w
        counts['vo2max'] += v

    counts['ftp'] += sync_intervals_ftp(
        profile,
        client,
        remote_activities=remote_activities,
        recorded_on=newest,
    )
    counts['vo2max'] += backfill_vo2max_from_activities(profile, oldest, newest)
    return counts


def backfill_vo2max_from_activities(profile, oldest: date, newest: date) -> int:
    from activities.models import Activity

    written = 0
    qs = (
        Activity.objects.filter(
            profile=profile,
            vo2max__isnull=False,
            started_at__date__gte=oldest,
            started_at__date__lte=newest,
        )
        .only('id', 'started_at', 'vo2max')
        .order_by('started_at')
    )
    for activity in qs:
        day = dj_timezone.localtime(activity.started_at).date()
        sample = upsert_metric_sample(
            profile,
            metric=ProfileMetricSample.Metric.VO2MAX,
            recorded_on=day,
            value=activity.vo2max,
            source=ProfileMetricSample.Source.ACTIVITY,
            external_key=f'activity:{activity.pk}',
            update_profile_ftp=False,
        )
        if sample:
            written += 1
    return written


def _mark_garmin_metric_unsupported(key: str, exc: GarminApiError) -> None:
    if exc.status_code == 404:
        _UNSUPPORTED_GARMIN_METRICS.add(key)
        logger.info('Garmin metric endpoint %s marked unsupported (HTTP 404)', key)


def _sync_garmin_weight(profile, client: GarminClient, start: date, end: date) -> int:
    key = 'weight'
    if key in _UNSUPPORTED_GARMIN_METRICS:
        return 0
    try:
        raw = client.get_weight_range(start.isoformat(), end.isoformat())
    except GarminApiError as exc:
        _mark_garmin_metric_unsupported(key, exc)
        logger.warning('Garmin weight sync failed %s..%s: %s', start, end, exc)
        return 0
    return ingest_garmin_weight(profile, raw)


def _sync_garmin_ftp_stats(profile, client: GarminClient, start: date, end: date) -> int:
    key = 'biometric_stats'
    if key in _UNSUPPORTED_GARMIN_METRICS:
        return 0
    try:
        raw = client.get_biometric_stats(start.isoformat(), end.isoformat())
    except GarminApiError as exc:
        _mark_garmin_metric_unsupported(key, exc)
        logger.warning('Garmin biometric stats sync failed %s..%s: %s', start, end, exc)
        return 0
    return ingest_garmin_biometric_ftp(profile, raw)


def _sync_garmin_vo2max(profile, client: GarminClient, start: date, end: date) -> int:
    key = 'maxmet'
    if key in _UNSUPPORTED_GARMIN_METRICS:
        return 0
    try:
        raw = client.get_maxmet_daily(start.isoformat(), end.isoformat())
    except GarminApiError as exc:
        _mark_garmin_metric_unsupported(key, exc)
        logger.warning('Garmin VO2max sync failed %s..%s: %s', start, end, exc)
        return 0
    return ingest_garmin_vo2max(profile, raw)


def ingest_garmin_weight(profile, raw: Any) -> int:
    items = []
    if isinstance(raw, dict):
        items = raw.get('dateWeightList') or raw.get('weightList') or []
    elif isinstance(raw, list):
        items = raw
    if not isinstance(items, list):
        return 0

    written = 0
    for item in items:
        if not isinstance(item, dict):
            continue
        day = _extract_date(item)
        if not day:
            continue
        weight_kg = None
        if item.get('weight') is not None:
            # Garmin often stores grams
            grams = _to_decimal(item.get('weight'))
            if grams is not None:
                weight_kg = grams / Decimal('1000') if grams > Decimal('250') else grams
        if weight_kg is None and item.get('weightInGrams') is not None:
            grams = _to_decimal(item.get('weightInGrams'))
            if grams is not None:
                weight_kg = grams / Decimal('1000')
        if weight_kg is None:
            continue
        sample = upsert_metric_sample(
            profile,
            metric=ProfileMetricSample.Metric.WEIGHT,
            recorded_on=day,
            value=weight_kg,
            source=ProfileMetricSample.Source.GARMIN,
            external_key=str(item.get('samplePk') or item.get('version') or ''),
            update_profile_ftp=False,
        )
        if sample:
            written += 1
    return written


def ingest_garmin_biometric_ftp(profile, raw: Any) -> int:
    points = _iter_biometric_stat_points(raw)
    written = 0
    for day, ftp in points:
        sample = upsert_metric_sample(
            profile,
            metric=ProfileMetricSample.Metric.FTP,
            recorded_on=day,
            value=ftp,
            source=ProfileMetricSample.Source.GARMIN,
            update_profile_ftp=False,
        )
        if sample:
            written += 1
    return written


def ingest_garmin_vo2max(profile, raw: Any) -> int:
    by_day: dict[date, Decimal] = {}
    entries = raw if isinstance(raw, list) else (
        (raw or {}).get('metrics')
        or (raw or {}).get('calendarDateList')
        or (raw or {}).get('maxMetDataDTOList')
        or []
    )
    if isinstance(raw, dict) and not entries:
        # Single-day shape: {calendarDate, generic, cycling}
        entries = [raw]

    if not isinstance(entries, list):
        return 0

    for item in entries:
        if not isinstance(item, dict):
            continue
        day = _extract_date(item)
        if not day:
            continue
        value = _vo2_from_maxmet_item(item)
        if value is None:
            continue
        # Prefer cycling over running when both exist on same day (handled in _vo2).
        existing = by_day.get(day)
        if existing is None or value > existing:
            by_day[day] = value

    written = 0
    for day, value in sorted(by_day.items()):
        sample = upsert_metric_sample(
            profile,
            metric=ProfileMetricSample.Metric.VO2MAX,
            recorded_on=day,
            value=value,
            source=ProfileMetricSample.Source.GARMIN,
            update_profile_ftp=False,
        )
        if sample:
            written += 1
    return written


def ingest_intervals_wellness(profile, rows: list[dict]) -> tuple[int, int]:
    weight_n = 0
    vo2_n = 0
    for row in rows or []:
        if not isinstance(row, dict):
            continue
        day = _extract_date(row) or _parse_date_str(row.get('id'))
        if not day:
            continue
        if row.get('weight') is not None:
            sample = upsert_metric_sample(
                profile,
                metric=ProfileMetricSample.Metric.WEIGHT,
                recorded_on=day,
                value=row.get('weight'),
                source=ProfileMetricSample.Source.INTERVALS,
                update_profile_ftp=False,
            )
            if sample:
                weight_n += 1
        vo2 = row.get('vo2max') or row.get('vo2Max') or row.get('VO2max')
        if vo2 is not None:
            sample = upsert_metric_sample(
                profile,
                metric=ProfileMetricSample.Metric.VO2MAX,
                recorded_on=day,
                value=vo2,
                source=ProfileMetricSample.Source.INTERVALS,
                update_profile_ftp=False,
            )
            if sample:
                vo2_n += 1
    return weight_n, vo2_n


def sync_intervals_ftp(
    profile,
    client: IntervalsClient,
    *,
    remote_activities: Optional[list[dict]] = None,
    recorded_on: Optional[date] = None,
) -> int:
    written = 0
    day = recorded_on or dj_timezone.localdate()

    ftp = _ftp_from_intervals_athlete(client)
    if ftp:
        sample = upsert_metric_sample(
            profile,
            metric=ProfileMetricSample.Metric.FTP,
            recorded_on=day,
            value=ftp,
            source=ProfileMetricSample.Source.INTERVALS,
            external_key='athlete_ftp',
        )
        if sample:
            written += 1

    last_ftp = None
    for activity in remote_activities or []:
        if not isinstance(activity, dict):
            continue
        ftp_val = activity.get('icu_ftp') or activity.get('ftp')
        if ftp_val is None:
            continue
        try:
            ftp_int = int(float(ftp_val))
        except (TypeError, ValueError):
            continue
        if ftp_int <= 0 or ftp_int == last_ftp:
            continue
        act_day = _extract_date(activity) or _parse_date_str(
            (activity.get('start_date_local') or activity.get('start_date') or '')[:10]
        )
        if not act_day:
            continue
        sample = upsert_metric_sample(
            profile,
            metric=ProfileMetricSample.Metric.FTP,
            recorded_on=act_day,
            value=ftp_int,
            source=ProfileMetricSample.Source.INTERVALS,
            external_key=f"activity:{activity.get('id') or ''}",
            update_profile_ftp=False,
        )
        if sample:
            written += 1
            last_ftp = ftp_int
    return written


def _ftp_from_intervals_athlete(client: IntervalsClient) -> Optional[int]:
    try:
        settings_list = client.get_sport_settings()
    except IntervalsApiError:
        settings_list = []

    for item in settings_list:
        if not isinstance(item, dict):
            continue
        sport = str(item.get('type') or item.get('sport') or '').lower()
        if sport and sport not in ('ride', 'virtualride', 'cycling', 'bike', ''):
            continue
        for key in ('ftp', 'icu_ftp', 'functional_threshold_power'):
            if item.get(key) is not None:
                try:
                    return int(float(item[key]))
                except (TypeError, ValueError):
                    pass

    try:
        athlete = client.get_athlete()
    except IntervalsApiError:
        return None
    if not isinstance(athlete, dict):
        return None
    for key in ('ftp', 'icu_ftp'):
        if athlete.get(key) is not None:
            try:
                return int(float(athlete[key]))
            except (TypeError, ValueError):
                pass
    # Nested sport settings on athlete
    nested = athlete.get('sportSettings') or athlete.get('sport_settings') or []
    if isinstance(nested, list):
        for item in nested:
            if isinstance(item, dict) and item.get('ftp') is not None:
                try:
                    return int(float(item['ftp']))
                except (TypeError, ValueError):
                    pass
    return None


def _iter_biometric_stat_points(raw: Any) -> list[tuple[date, int]]:
    """Extract (date, ftp) pairs from Garmin biometric-service/stats payload."""
    points: list[tuple[date, int]] = []
    if raw is None:
        return points

    candidates: list[Any] = []
    if isinstance(raw, list):
        candidates = raw
    elif isinstance(raw, dict):
        for key in (
            'calendarDateList',
            'dailyStats',
            'stats',
            'entries',
            'values',
            'functionalThresholdPowerList',
        ):
            if isinstance(raw.get(key), list):
                candidates = raw[key]
                break
        if not candidates and raw.get('calendarDate'):
            candidates = [raw]

    for item in candidates:
        if not isinstance(item, dict):
            continue
        day = _extract_date(item)
        ftp = None
        for key in (
            'functionalThresholdPower',
            'ftp',
            'FTP',
            'cyclingFtp',
            'functionalThresholdPowerCycling',
        ):
            if item.get(key) is not None:
                try:
                    ftp = int(float(item[key]))
                    break
                except (TypeError, ValueError):
                    continue
        # Nested biometric object
        bio = item.get('biometric') or item.get('stats') or {}
        if ftp is None and isinstance(bio, dict):
            for key in ('functionalThresholdPower', 'ftp', 'FTP'):
                if bio.get(key) is not None:
                    try:
                        ftp = int(float(bio[key]))
                        break
                    except (TypeError, ValueError):
                        continue
        if day and ftp and ftp > 0:
            points.append((day, ftp))
    return points


def _vo2_from_maxmet_item(item: dict) -> Optional[Decimal]:
    # Prefer cycling VO2max over running/generic.
    for key in (
        'cycling',
        'vo2MaxCycling',
        'cyclingVO2MaxValue',
        'generic',
        'vo2Max',
        'vo2MaxValue',
        'vO2MaxValue',
        'running',
    ):
        block = item.get(key)
        if isinstance(block, dict):
            for nested in ('vo2MaxValue', 'vO2MaxValue', 'value', 'vo2Max'):
                if block.get(nested) is not None:
                    dec = _to_decimal(block[nested])
                    if dec is not None and dec > 0:
                        return dec
        elif block is not None and key not in ('cycling', 'generic', 'running'):
            dec = _to_decimal(block)
            if dec is not None and dec > 0:
                return dec

    # Nested lists under maxMetDataDTOList on the day item
    nested_list = item.get('maxMetDataDTOList') or item.get('metrics')
    if isinstance(nested_list, list):
        cycling_val = None
        other_val = None
        for entry in nested_list:
            if not isinstance(entry, dict):
                continue
            val = _to_decimal(
                entry.get('vo2MaxValue')
                or entry.get('vO2MaxValue')
                or entry.get('value')
            )
            if val is None or val <= 0:
                continue
            sport = str(entry.get('sport') or entry.get('activityType') or '').lower()
            if 'cycl' in sport or 'bike' in sport:
                cycling_val = val
            else:
                other_val = val
        return cycling_val or other_val
    return None


def _extract_date(item: dict) -> Optional[date]:
    for key in (
        'calendarDate',
        'date',
        'day',
        'start_date_local',
        'start_date',
        'id',
        'datetime',
        'timestamp',
    ):
        raw = item.get(key)
        parsed = _parse_date_str(raw)
        if parsed:
            return parsed
        if isinstance(raw, (int, float)) and raw > 1_000_000_000:
            # epoch ms or s
            try:
                seconds = raw / 1000 if raw > 1e12 else raw
                return date.fromtimestamp(seconds)
            except (OverflowError, OSError, ValueError):
                continue
    return None


def _parse_date_str(value) -> Optional[date]:
    from datetime import datetime as dt

    if value is None:
        return None
    if isinstance(value, dt):
        return value.date()
    if isinstance(value, date):
        return value
    text = str(value).strip()
    if not text:
        return None
    text = text[:10]
    try:
        return date.fromisoformat(text)
    except ValueError:
        return None
