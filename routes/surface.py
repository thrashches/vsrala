"""Enrich route track with OSM surface tags via Overpass API."""

from __future__ import annotations

import logging
from typing import Any, Optional

import requests
from django.conf import settings

from .models import Route, haversine_m

logger = logging.getLogger(__name__)

SAMPLE_SPACING_M = 40.0
MATCH_RADIUS_M = 30.0
OVERPASS_TIMEOUT = 60

SURFACE_ALIASES = {
    'asphalt': 'asphalt',
    'paved': 'asphalt',
    'concrete': 'concrete',
    'cement': 'concrete',
    'paving_stones': 'paving_stones',
    'sett': 'paving_stones',
    'cobblestone': 'paving_stones',
    'brick': 'paving_stones',
    'gravel': 'gravel',
    'fine_gravel': 'gravel',
    'compacted': 'gravel',
    'pebblestone': 'gravel',
    'dirt': 'dirt',
    'earth': 'dirt',
    'ground': 'dirt',
    'mud': 'dirt',
    'sand': 'dirt',
    'grass': 'grass',
    'unpaved': 'dirt',
    'wood': 'unknown',
    'metal': 'unknown',
}

HIGHWAY_FALLBACK = {
    'motorway': 'asphalt',
    'trunk': 'asphalt',
    'primary': 'asphalt',
    'secondary': 'asphalt',
    'tertiary': 'asphalt',
    'unclassified': 'asphalt',
    'residential': 'asphalt',
    'living_street': 'asphalt',
    'service': 'asphalt',
    'cycleway': 'asphalt',
    'path': 'dirt',
    'footway': 'paving_stones',
    'track': 'dirt',
    'bridleway': 'dirt',
}


def normalize_surface(tags: dict) -> str:
    raw = (tags.get('surface') or '').strip().lower()
    if raw:
        # Take first value if semicolon-separated.
        raw = raw.split(';')[0].strip()
        if raw in SURFACE_ALIASES:
            return SURFACE_ALIASES[raw]
        return raw if raw else 'unknown'
    highway = (tags.get('highway') or '').strip().lower()
    return HIGHWAY_FALLBACK.get(highway, 'unknown')


def _extract_latlngs(points: list) -> list[tuple[float, float]]:
    out: list[tuple[float, float]] = []
    for p in points or []:
        if not p or len(p) < 2:
            continue
        try:
            out.append((float(p[0]), float(p[1])))
        except (TypeError, ValueError):
            continue
    return out


def downsample_by_distance(
    points: list[tuple[float, float]],
    spacing_m: float = SAMPLE_SPACING_M,
) -> list[tuple[int, float, float]]:
    """Return [(original_index, lat, lon), ...] sampled along the track."""
    if not points:
        return []
    samples = [(0, points[0][0], points[0][1])]
    acc = 0.0
    for i in range(1, len(points)):
        d = haversine_m(points[i - 1][0], points[i - 1][1], points[i][0], points[i][1])
        acc += d
        if acc >= spacing_m:
            samples.append((i, points[i][0], points[i][1]))
            acc = 0.0
    last_i = len(points) - 1
    if samples[-1][0] != last_i:
        samples.append((last_i, points[last_i][0], points[last_i][1]))
    return samples


def _bbox(points: list[tuple[float, float]], pad: float = 0.002) -> tuple[float, float, float, float]:
    lats = [p[0] for p in points]
    lons = [p[1] for p in points]
    return min(lats) - pad, min(lons) - pad, max(lats) + pad, max(lons) + pad


def build_overpass_query(south: float, west: float, north: float, east: float) -> str:
    return (
        f'[out:json][timeout:{OVERPASS_TIMEOUT}];\n'
        f'way["highway"]({south},{west},{north},{east});\n'
        f'out tags center;\n'
    )


def fetch_overpass_ways(south: float, west: float, north: float, east: float) -> list[dict]:
    url = getattr(settings, 'OVERPASS_URL', 'https://overpass-api.de/api/interpreter')
    query = build_overpass_query(south, west, north, east)
    headers = {
        'User-Agent': getattr(settings, 'OVERPASS_USER_AGENT', 'vsrala/1.0 (route surfaces)'),
    }
    resp = requests.post(url, data={'data': query}, headers=headers, timeout=OVERPASS_TIMEOUT + 10)
    resp.raise_for_status()
    data = resp.json()
    return [el for el in data.get('elements', []) if el.get('type') == 'way']


def _way_center(way: dict) -> Optional[tuple[float, float]]:
    center = way.get('center') or {}
    lat, lon = center.get('lat'), center.get('lon')
    if lat is None or lon is None:
        return None
    return float(lat), float(lon)


def match_surfaces_to_points(
    points: list[tuple[float, float]],
    ways: list[dict],
    radius_m: float = MATCH_RADIUS_M,
) -> list[str]:
    """Assign a surface label to each track point index."""
    centers: list[tuple[float, float, str]] = []
    for way in ways:
        c = _way_center(way)
        if not c:
            continue
        centers.append((c[0], c[1], normalize_surface(way.get('tags') or {})))

    labels: list[str] = []
    for lat, lon in points:
        best = 'unknown'
        best_d = radius_m
        for wlat, wlon, surface in centers:
            d = haversine_m(lat, lon, wlat, wlon)
            if d <= best_d:
                best_d = d
                best = surface
        labels.append(best)
    return labels


def collapse_to_segments(
    points: list[tuple[float, float]],
    labels: list[str],
) -> list[dict[str, Any]]:
    if not points or not labels:
        return []
    segments: list[dict[str, Any]] = []
    start = 0
    current = labels[0]
    for i in range(1, len(labels)):
        if labels[i] != current:
            dist = 0.0
            for j in range(start + 1, i + 1):
                dist += haversine_m(points[j - 1][0], points[j - 1][1], points[j][0], points[j][1])
            segments.append({
                'start_idx': start,
                'end_idx': i,
                'surface': current,
                'distance_m': round(dist, 1),
            })
            start = i
            current = labels[i]
    dist = 0.0
    for j in range(start + 1, len(points)):
        dist += haversine_m(points[j - 1][0], points[j - 1][1], points[j][0], points[j][1])
    segments.append({
        'start_idx': start,
        'end_idx': len(points) - 1,
        'surface': current,
        'distance_m': round(dist, 1),
    })
    return segments


def enrich_route(route: Route) -> Route:
    points = _extract_latlngs(route.track_points or [])
    if len(points) < 2:
        route.surface_segments = []
        route.surface_status = Route.SurfaceStatus.SKIPPED
        route.save(update_fields=['surface_segments', 'surface_status', 'updated_at'])
        return route

    # Work on full-resolution points for segments; match via nearby way centers.
    south, west, north, east = _bbox(points)
    ways = fetch_overpass_ways(south, west, north, east)
    labels = match_surfaces_to_points(points, ways)
    segments = collapse_to_segments(points, labels)
    route.surface_segments = segments
    route.surface_status = Route.SurfaceStatus.READY
    route.save(update_fields=['surface_segments', 'surface_status', 'updated_at'])
    return route
