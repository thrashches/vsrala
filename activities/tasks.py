from __future__ import annotations

import logging

from celery import shared_task

from activities.map_preview import apply_map_preview
from activities.models import Activity

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
