"""Helpers for creating routes from GPX / activities."""

from __future__ import annotations

from decimal import Decimal
from io import BytesIO

from django.core.files.base import ContentFile

from activities.map_preview import render_map_preview_image
from activities.parsers import ParsedTrack, TrackParseError, parse_track

from .models import Route, distance_km_from_points, strip_time_from_points


def apply_route_map_preview(route: Route, *, save: bool = True) -> bool:
    img = render_map_preview_image(route.track_points or [])
    old_name = route.map_preview.name if route.map_preview else ''

    if img is None:
        if route.map_preview:
            route.map_preview.delete(save=False)
        if save and route.pk:
            route.save(update_fields=['map_preview'])
        return False

    buf = BytesIO()
    img.save(buf, format='PNG', optimize=True)
    content = ContentFile(buf.getvalue(), name='map_preview.png')
    if old_name:
        route.map_preview.delete(save=False)
    route.map_preview.save('map_preview.png', content, save=False)
    if save and route.pk:
        route.save(update_fields=['map_preview'])
    return True


def points_from_parsed(parsed: ParsedTrack) -> list:
    return strip_time_from_points(parsed.points or [])


def apply_parsed_to_route(route: Route, parsed: ParsedTrack) -> None:
    points = points_from_parsed(parsed)
    route.track_points = points
    route.distance = Decimal(str(distance_km_from_points(points) or parsed.distance_km or 0))
    route.elevation_gain = parsed.elevation_gain
    route.elevation_loss = parsed.elevation_loss


def slice_track_points(points: list, start_idx: int, end_idx: int) -> list:
    pts = strip_time_from_points(points)
    if not pts:
        return []
    n = len(pts)
    start = max(0, min(int(start_idx), n - 1))
    end = max(0, min(int(end_idx), n - 1))
    if end < start:
        start, end = end, start
    if end == start:
        # Keep at least two points when possible for a drawable line.
        if start + 1 < n:
            end = start + 1
        elif start > 0:
            start = start - 1
    return pts[start:end + 1]


def create_route_from_gpx(
    *,
    profile,
    file_bytes: bytes,
    filename: str,
    title: str = '',
    description: str = '',
    visibility: str = Route.Visibility.PRIVATE,
) -> Route:
    parsed = parse_track(BytesIO(file_bytes), filename=filename)
    points = points_from_parsed(parsed)
    if len(points) < 2:
        raise TrackParseError('В файле нет GPS-точек маршрута')

    route = Route(
        profile=profile,
        title=(title or '').strip() or (filename.rsplit('.', 1)[0] if filename else 'Маршрут'),
        description=(description or '').strip(),
        visibility=visibility or Route.Visibility.PRIVATE,
    )
    apply_parsed_to_route(route, parsed)
    route.surface_status = Route.SurfaceStatus.PENDING
    route.source_gpx = ContentFile(file_bytes, name=filename)
    route.save()
    apply_route_map_preview(route)
    return route


def create_route_from_activity(
    *,
    profile,
    activity,
    start_idx: int,
    end_idx: int,
    title: str = '',
    description: str = '',
    visibility: str = Route.Visibility.PRIVATE,
) -> Route:
    if activity.profile_id != profile.pk:
        raise PermissionError('Можно создать маршрут только из своей тренировки')
    points = slice_track_points(activity.track_points or [], start_idx, end_idx)
    if len(points) < 2:
        raise ValueError('Недостаточно точек для маршрута')

    route = Route(
        profile=profile,
        title=(title or '').strip() or (activity.title or 'Маршрут'),
        description=(description or '').strip(),
        visibility=visibility or Route.Visibility.PRIVATE,
        track_points=points,
        distance=Decimal(str(distance_km_from_points(points))),
        elevation_gain=None,
        elevation_loss=None,
        source_activity=activity,
        surface_status=Route.SurfaceStatus.PENDING,
    )
    route.save()
    apply_route_map_preview(route)
    return route


def enqueue_surface_enrichment(route_id: int) -> None:
    from .tasks import enrich_route_surfaces
    enrich_route_surfaces.delay(route_id)
