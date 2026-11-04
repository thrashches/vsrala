"""Canonical activity types and external-source mappings."""
from __future__ import annotations

from typing import Optional

from activities.models import ActivityType

# (slug, name, sort_order) — cycling and running first.
STANDARD_TYPES = (
    ('road_cycling', 'Шоссейный велосипед', 10),
    ('mtb', 'Горный велосипед', 20),
    ('gravel', 'Кроссовый велосипед', 30),
    ('track_cycling', 'Трековый велосипед', 40),
    ('running', 'Бег', 50),
    ('swimming', 'Заплыв', 60),
    ('walking', 'Ходьба', 70),
    ('skiing', 'Лыжи', 80),
    ('rowing', 'Гребля', 90),
)

# Foot sports: show pace (min/km) instead of speed (km/h).
PACE_SPORT_SLUGS = frozenset({'running', 'walking', 'skiing'})

INTERVALS_TYPE_MAP = {
    'Ride': 'Шоссейный велосипед',
    'VirtualRide': 'Шоссейный велосипед',
    'MountainBikeRide': 'Горный велосипед',
    'GravelRide': 'Кроссовый велосипед',
    'TrackCycling': 'Трековый велосипед',
    'Run': 'Бег',
    'VirtualRun': 'Бег',
    'Swim': 'Заплыв',
    'Walk': 'Ходьба',
    'Hike': 'Ходьба',
    'NordicSki': 'Лыжи',
    'BackcountrySki': 'Лыжи',
    'AlpineSki': 'Лыжи',
    'Rowing': 'Гребля',
    'VirtualRow': 'Гребля',
}

GARMIN_TYPE_MAP = {
    'cycling': 'Шоссейный велосипед',
    'road_biking': 'Шоссейный велосипед',
    'virtual_ride': 'Шоссейный велосипед',
    'indoor_cycling': 'Шоссейный велосипед',
    'mountain_biking': 'Горный велосипед',
    'gravel_cycling': 'Кроссовый велосипед',
    'track_cycling': 'Трековый велосипед',
    'running': 'Бег',
    'treadmill_running': 'Бег',
    'trail_running': 'Бег',
    'swimming': 'Заплыв',
    'lap_swimming': 'Заплыв',
    'open_water_swimming': 'Заплыв',
    'walking': 'Ходьба',
    'hiking': 'Ходьба',
    'resort_skiing': 'Лыжи',
    'cross_country_skiing': 'Лыжи',
    'backcountry_skiing': 'Лыжи',
    'resort_snowboarding': 'Лыжи',
    'rowing': 'Гребля',
    'indoor_rowing': 'Гребля',
}

# FIT sport enum names (fitparse) / common aliases → local ActivityType name.
FIT_SPORT_MAP = {
    'cycling': 'Шоссейный велосипед',
    'cycling_indoor': 'Шоссейный велосипед',
    'road': 'Шоссейный велосипед',
    'mountain': 'Горный велосипед',
    'cyclocross': 'Кроссовый велосипед',
    'gravel_cycling': 'Кроссовый велосипед',
    'track_cycling': 'Трековый велосипед',
    'running': 'Бег',
    'treadmill': 'Бег',
    'trail_run': 'Бег',
    'swimming': 'Заплыв',
    'lap_swimming': 'Заплыв',
    'open_water': 'Заплыв',
    'walking': 'Ходьба',
    'hiking': 'Ходьба',
    'cross_country_skiing': 'Лыжи',
    'alpine_skiing': 'Лыжи',
    'snowboarding': 'Лыжи',
    'rowing': 'Гребля',
}


def ensure_activity_type(name: str) -> ActivityType:
    """Return ActivityType by Russian name, creating from STANDARD_TYPES when known."""
    slug = ''
    sort_order = 1000
    for std_slug, std_name, std_order in STANDARD_TYPES:
        if std_name == name:
            slug = std_slug
            sort_order = std_order
            break

    existing = ActivityType.objects.filter(name=name).first()
    if existing:
        updates = []
        if slug and not existing.slug:
            existing.slug = slug
            updates.append('slug')
        if slug and existing.sort_order != sort_order:
            existing.sort_order = sort_order
            updates.append('sort_order')
        if updates:
            existing.save(update_fields=updates)
        return existing

    if slug:
        obj, _ = ActivityType.objects.get_or_create(
            slug=slug,
            defaults={'name': name, 'sort_order': sort_order},
        )
        if obj.name != name:
            obj.name = name
            obj.sort_order = sort_order
            obj.save(update_fields=['name', 'sort_order'])
        return obj

    return ActivityType.objects.create(name=name, sort_order=sort_order)


def resolve_from_map(raw: Optional[str], mapping: dict) -> Optional[ActivityType]:
    if not raw:
        return None
    name = mapping.get(raw) or mapping.get(str(raw).lower())
    if not name:
        return None
    return ensure_activity_type(name)


def resolve_intervals_type(intervals_type: Optional[str]) -> Optional[ActivityType]:
    return resolve_from_map(intervals_type, INTERVALS_TYPE_MAP)


def resolve_garmin_type(type_key: Optional[str]) -> Optional[ActivityType]:
    return resolve_from_map(type_key, GARMIN_TYPE_MAP)


def resolve_fit_sport(sport: Optional[str], sub_sport: Optional[str] = None) -> Optional[ActivityType]:
    for key in (sub_sport, sport):
        if not key:
            continue
        normalized = str(key).strip().lower().replace(' ', '_')
        result = resolve_from_map(normalized, FIT_SPORT_MAP)
        if result:
            return result
    return None


def seed_standard_types() -> None:
    for slug, name, sort_order in STANDARD_TYPES:
        obj, created = ActivityType.objects.get_or_create(
            name=name,
            defaults={'slug': slug, 'sort_order': sort_order},
        )
        if not created:
            updates = []
            if not obj.slug:
                obj.slug = slug
                updates.append('slug')
            if obj.sort_order != sort_order:
                obj.sort_order = sort_order
                updates.append('sort_order')
            if updates:
                obj.save(update_fields=updates)


def activity_uses_pace(activity_type: Optional[ActivityType]) -> bool:
    """True for foot sports where pace (min/km) is preferred over speed."""
    if activity_type is None:
        return False
    slug = (getattr(activity_type, 'slug', None) or '').strip().lower()
    return slug in PACE_SPORT_SLUGS
