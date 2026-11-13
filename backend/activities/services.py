from __future__ import annotations

from datetime import datetime, timezone
from io import BytesIO

from django.core.files.base import ContentFile

from activities.activity_types import resolve_fit_sport
from activities.map_preview import apply_map_preview
from activities.models import Activity
from activities.parsers import TrackParseError, parse_track
from activities.parsers.fit import read_fit_sport
from activities.zone_timeline import apply_zone_timeline


def create_activity_from_upload(
    *,
    profile,
    track_file,
    title: str = '',
    description: str = '',
    activity_type=None,
) -> Activity:
    """Parse uploaded GPX/FIT, create Activity, apply map/zone side effects."""
    from activities.tasks import enqueue_activity_weather

    filename = track_file.name
    track_file.seek(0)
    file_bytes = track_file.read()

    try:
        parsed = parse_track(BytesIO(file_bytes), filename=filename)
    except TrackParseError:
        raise

    if activity_type is None:
        activity_type = resolve_fit_sport(parsed.sport, parsed.sub_sport)

    activity = Activity(
        profile=profile,
        title=title or '',
        description=description or '',
        activity_type=activity_type,
        started_at=datetime.now(timezone.utc),
    )

    activity.apply_parsed_track(parsed)
    activity.track_file = ContentFile(file_bytes, name=filename)
    activity.save()
    apply_map_preview(activity)
    apply_zone_timeline(activity)
    # Weather (Open-Meteo) off hot path so upload stays responsive.
    enqueue_activity_weather(activity.pk)
    return activity


def resolve_activity_type_from_fit(activity: Activity):
    """
    Infer ActivityType from activity.track_file when it is a FIT file.
    Returns (activity_type | None, skip_reason | None).
    """
    if not activity.track_file:
        return None, 'нет файла'
    filename = (activity.track_file.name or '').lower()
    if not filename.endswith('.fit'):
        return None, 'не FIT'
    try:
        with activity.track_file.open('rb') as fh:
            sport, sub_sport = read_fit_sport(fh)
    except TrackParseError as exc:
        return None, str(exc)
    except Exception as exc:
        return None, f'ошибка чтения: {exc}'

    activity_type = resolve_fit_sport(sport, sub_sport)
    if activity_type is None:
        detail = '/'.join(p for p in (sport, sub_sport) if p) or 'пусто'
        return None, f'неизвестный sport ({detail})'
    return activity_type, None


def update_activity_types_from_fit(queryset) -> dict:
    """Update activity_type from FIT for each activity in queryset. Returns counters."""
    updated = 0
    unchanged = 0
    skipped = 0
    skip_reasons: dict[str, int] = {}

    for activity in queryset.iterator():
        activity_type, reason = resolve_activity_type_from_fit(activity)
        if activity_type is None:
            skipped += 1
            skip_reasons[reason or 'пропуск'] = skip_reasons.get(reason or 'пропуск', 0) + 1
            continue
        if activity.activity_type_id == activity_type.pk:
            unchanged += 1
            continue
        activity.activity_type = activity_type
        activity.save(update_fields=['activity_type'])
        updated += 1

    return {
        'updated': updated,
        'unchanged': unchanged,
        'skipped': skipped,
        'skip_reasons': skip_reasons,
    }
