from __future__ import annotations

from datetime import datetime, timezone
from io import BytesIO

from django.core.files.base import ContentFile

from activities.map_preview import apply_map_preview
from activities.models import Activity
from activities.parsers import TrackParseError, parse_track
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
    filename = track_file.name
    track_file.seek(0)
    file_bytes = track_file.read()

    activity = Activity(
        profile=profile,
        title=title or '',
        description=description or '',
        activity_type=activity_type,
        started_at=datetime.now(timezone.utc),
    )

    try:
        parsed = parse_track(BytesIO(file_bytes), filename=filename)
    except TrackParseError:
        raise

    activity.apply_parsed_track(parsed)
    activity.track_file = ContentFile(file_bytes, name=filename)
    activity.save()
    apply_map_preview(activity)
    apply_zone_timeline(activity)
    return activity
