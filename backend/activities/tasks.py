from __future__ import annotations

import logging

from celery import shared_task

from activities.map_preview import apply_map_preview
from activities.models import Activity
from activities.services import update_activity_types_from_fit
from activities.weather import attach_weather
from activities.zone_timeline import apply_zone_timeline

logger = logging.getLogger(__name__)


@shared_task
def enrich_activity_after_import(activity_id: int) -> dict:
    """Generate map preview, zone timeline, and weather after import (off hot path)."""
    try:
        activity = Activity.objects.get(pk=activity_id)
    except Activity.DoesNotExist:
        logger.warning('Activity %s not found for post-import enrichment', activity_id)
        return {'ok': False, 'error': 'not_found'}

    preview_ok = False
    zones_ok = False
    weather_ok = False
    try:
        preview_ok = bool(apply_map_preview(activity))
    except Exception:
        logger.exception('Map preview failed for activity %s', activity_id)
    try:
        zones_ok = bool(apply_zone_timeline(activity))
    except Exception:
        logger.exception('Zone timeline failed for activity %s', activity_id)
    try:
        # Reload in case map/zone saved other fields; weather needs track_points.
        activity.refresh_from_db()
        weather_ok = bool(attach_weather(activity))
    except Exception:
        logger.exception('Weather attach failed for activity %s', activity_id)
    return {
        'ok': True,
        'map_preview': preview_ok,
        'zone_timeline': zones_ok,
        'weather': weather_ok,
    }


def enqueue_activity_enrichment(activity_id: int) -> None:
    """Fire-and-forget enrichment; ignore broker errors during sync."""
    try:
        enrich_activity_after_import.delay(activity_id)
    except Exception:
        logger.exception('Failed to enqueue enrichment for activity %s', activity_id)


@shared_task(ignore_result=True)
def attach_activity_weather_task(activity_id: int) -> dict:
    """Attach Open-Meteo weather for a single activity (off hot path)."""
    try:
        activity = Activity.objects.get(pk=activity_id)
    except Activity.DoesNotExist:
        logger.warning('Activity %s not found for weather attach', activity_id)
        return {'ok': False, 'error': 'not_found'}
    try:
        ok = bool(attach_weather(activity))
    except Exception:
        logger.exception('Weather attach failed for activity %s', activity_id)
        return {'ok': False, 'error': 'exception'}
    return {'ok': True, 'weather': ok}


def enqueue_activity_weather(activity_id: int) -> None:
    """Fire-and-forget weather attach; ignore broker errors."""
    try:
        attach_activity_weather_task.apply_async(args=(activity_id,), ignore_result=True)
    except Exception:
        logger.exception('Failed to enqueue weather for activity %s', activity_id)


@shared_task
def generate_map_previews_for_activities(activity_ids: list[int]) -> dict:
    """Regenerate map_preview for the given activity ids."""
    ok = 0
    skipped = 0
    for activity_id in activity_ids:
        try:
            activity = Activity.objects.get(pk=activity_id)
        except Activity.DoesNotExist:
            logger.warning('Activity %s not found for map preview generation', activity_id)
            skipped += 1
            continue
        try:
            if apply_map_preview(activity):
                ok += 1
            else:
                skipped += 1
        except Exception:
            logger.exception('Failed to generate map preview for activity %s', activity_id)
            skipped += 1
    return {'ok': True, 'generated': ok, 'skipped': skipped, 'total': len(activity_ids)}


@shared_task
def update_activity_types_from_fit_task(activity_ids: list[int]) -> dict:
    """Infer activity_type from FIT track files for the given activity ids."""
    if not activity_ids:
        return {'ok': True, 'updated': 0, 'unchanged': 0, 'skipped': 0, 'total': 0}
    qs = Activity.objects.filter(pk__in=activity_ids)
    result = update_activity_types_from_fit(qs)
    logger.info(
        'FIT activity types: updated=%s unchanged=%s skipped=%s total=%s reasons=%s',
        result['updated'],
        result['unchanged'],
        result['skipped'],
        len(activity_ids),
        result.get('skip_reasons') or {},
    )
    return {'ok': True, 'total': len(activity_ids), **result}
