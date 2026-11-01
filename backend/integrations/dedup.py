from __future__ import annotations

from datetime import timedelta
from decimal import Decimal
from typing import Any, Optional

from activities.models import Activity

SOURCE_GARMIN = 'garmin'
SOURCE_INTERVALS = 'intervals'

# Match window for cross-source duplicates.
STARTED_AT_TOLERANCE = timedelta(seconds=90)
DISTANCE_REL_TOLERANCE = Decimal('0.02')  # 2%
DURATION_REL_TOLERANCE = 0.05  # 5%


def _as_decimal(value) -> Decimal:
    if value is None:
        return Decimal('0')
    if isinstance(value, Decimal):
        return value
    try:
        return Decimal(str(value))
    except Exception:
        return Decimal('0')


def _duration_seconds(duration) -> float:
    if duration is None:
        return 0.0
    try:
        return float(duration.total_seconds())
    except AttributeError:
        return float(duration or 0)


def _distance_matches(a: Decimal, b: Decimal) -> bool:
    if a <= Decimal('0.05') and b <= Decimal('0.05'):
        return True  # both near-zero (indoor / no GPS)
    larger = max(a, b)
    if larger <= 0:
        return True
    return abs(a - b) / larger <= DISTANCE_REL_TOLERANCE


def _duration_matches(a_sec: float, b_sec: float) -> bool:
    if a_sec <= 1 and b_sec <= 1:
        return True
    larger = max(a_sec, b_sec)
    if larger <= 0:
        return True
    return abs(a_sec - b_sec) / larger <= DURATION_REL_TOLERANCE


def activity_has_external_id(activity: Activity, source: str, external_id: str) -> bool:
    if not external_id:
        return False
    if activity.external_source == source and activity.external_id == external_id:
        return True
    refs = activity.external_refs or {}
    return str(refs.get(source) or '') == str(external_id)


def find_activity_by_external_id(profile, source: str, external_id: str) -> Optional[Activity]:
    if not external_id:
        return None
    external_id = str(external_id)
    direct = Activity.objects.filter(
        profile=profile,
        external_source=source,
        external_id=external_id,
    ).first()
    if direct:
        return direct
    # JSONField __contains is reliable on Postgres; fall back to Python scan for others.
    try:
        via_refs = Activity.objects.filter(
            profile=profile,
            external_refs__contains={source: external_id},
        ).first()
        if via_refs:
            return via_refs
    except Exception:
        pass
    for activity in Activity.objects.filter(profile=profile).exclude(external_refs={}).exclude(external_refs=None):
        refs = activity.external_refs or {}
        if str(refs.get(source) or '') == external_id:
            return activity
    return None


def find_duplicate_activity(
    profile,
    *,
    started_at,
    distance,
    duration,
    exclude_pk: Optional[int] = None,
) -> Optional[Activity]:
    """Find an existing activity that likely matches the same workout."""
    if started_at is None:
        return None

    window_start = started_at - STARTED_AT_TOLERANCE
    window_end = started_at + STARTED_AT_TOLERANCE
    qs = Activity.objects.filter(
        profile=profile,
        started_at__gte=window_start,
        started_at__lte=window_end,
    )
    if exclude_pk:
        qs = qs.exclude(pk=exclude_pk)

    target_distance = _as_decimal(distance)
    target_duration = _duration_seconds(duration)

    for candidate in qs:
        if not _distance_matches(target_distance, _as_decimal(candidate.distance)):
            continue
        if not _duration_matches(target_duration, _duration_seconds(candidate.duration)):
            continue
        return candidate
    return None


# Fields that Garmin wins on conflict when incoming source is garmin.
_METRIC_FIELDS = (
    'title',
    'description',
    'activity_type',
    'duration',
    'duration_active',
    'distance',
    'avg_speed',
    'avg_moving_speed',
    'max_speed',
    'avg_hr',
    'max_hr',
    'avg_power',
    'max_power',
    'normalized_power',
    'tss',
    'avg_cadence',
    'max_cadence',
    'elevation_gain',
    'elevation_loss',
    'elevation_min',
    'elevation_max',
    'is_indoor',
    'calories',
    'aerobic_training_effect',
    'anaerobic_training_effect',
    'device_name',
    'avg_temperature',
    'vo2max',
)

_TRACK_FIELDS = ('track_points', 'streams', 'track_file')


def _is_empty(value: Any) -> bool:
    if value is None:
        return True
    if value == '':
        return True
    if value == [] or value == {}:
        return True
    return False


def set_external_ref(activity: Activity, source: str, external_id: str) -> None:
    refs = dict(activity.external_refs or {})
    refs[source] = str(external_id)
    activity.external_refs = refs
    # Canonical source prefers Garmin; otherwise keep existing or set first source.
    if source == SOURCE_GARMIN:
        activity.external_source = SOURCE_GARMIN
        activity.external_id = str(external_id)
    elif not activity.external_source:
        activity.external_source = source
        activity.external_id = str(external_id)


def merge_activity(
    existing: Activity,
    *,
    source: str,
    external_id: str,
    field_values: dict[str, Any],
    prefer_incoming: bool,
) -> Activity:
    """
    Enrich existing activity with incoming fields and link external id.

    prefer_incoming=True: non-empty incoming values overwrite (Garmin path).
    prefer_incoming=False: only fill empty fields on existing (Intervals into Garmin).
    """
    set_external_ref(existing, source, external_id)
    update_fields = ['external_source', 'external_id', 'external_refs']

    for name in _METRIC_FIELDS:
        if name not in field_values:
            continue
        incoming = field_values[name]
        if _is_empty(incoming):
            continue
        current = getattr(existing, name, None)
        if prefer_incoming or _is_empty(current):
            setattr(existing, name, incoming)
            update_fields.append(name)

    for name in _TRACK_FIELDS:
        if name not in field_values:
            continue
        incoming = field_values[name]
        if _is_empty(incoming):
            continue
        current = getattr(existing, name, None)
        # Prefer Garmin track; for intervals-only fill if existing has no track.
        if prefer_incoming or _is_empty(current):
            setattr(existing, name, incoming)
            update_fields.append(name)

    # started_at: keep Garmin/existing; only set if empty (shouldn't happen)
    if 'started_at' in field_values and field_values['started_at'] and prefer_incoming:
        existing.started_at = field_values['started_at']
        update_fields.append('started_at')

    existing.save(update_fields=list(dict.fromkeys(update_fields)))
    return existing


def activity_field_values_from_instance(activity: Activity) -> dict[str, Any]:
    values = {}
    for name in _METRIC_FIELDS + _TRACK_FIELDS + ('started_at',):
        values[name] = getattr(activity, name, None)
    return values
