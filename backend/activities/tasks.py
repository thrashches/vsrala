from __future__ import annotations

import logging

from celery import shared_task

from activities.map_preview import apply_map_preview
from activities.models import Activity
from activities.services import update_activity_types_from_fit

logger = logging.getLogger(__name__)


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
