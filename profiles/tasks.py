from __future__ import annotations

import logging

from celery import shared_task

from profiles.models import Profile
from profiles.photo_preview import apply_photo_preview

logger = logging.getLogger(__name__)


@shared_task
def generate_photo_previews_for_profiles(profile_ids: list[int]) -> dict:
    """Regenerate photo_preview for the given profile ids."""
    ok = 0
    skipped = 0
    for profile_id in profile_ids:
        try:
            profile = Profile.objects.get(pk=profile_id)
        except Profile.DoesNotExist:
            logger.warning('Profile %s not found for photo preview generation', profile_id)
            skipped += 1
            continue
        try:
            if apply_photo_preview(profile):
                ok += 1
            else:
                skipped += 1
        except Exception:
            logger.exception('Failed to generate photo preview for profile %s', profile_id)
            skipped += 1
    return {'ok': True, 'generated': ok, 'skipped': skipped, 'total': len(profile_ids)}
