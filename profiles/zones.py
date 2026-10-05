"""Joe Friel / intervals.icu default training zones (7 zones)."""

from __future__ import annotations

from typing import Any, Optional

POWER_ZONE_NAMES = (
    'Recovery',
    'Endurance',
    'Tempo',
    'Threshold',
    'VO2max',
    'Anaerobic',
    'Neuromuscular',
)

# Upper boundaries as % of FTP for zones 1–6; zone 7 is open-ended.
POWER_ZONE_UPPER_PCTS = (55, 75, 90, 105, 120, 150)

HR_ZONE_NAMES = (
    'Recovery',
    'Aerobic',
    'Tempo',
    'SubThreshold',
    'SuperThreshold',
    'Aerobic Capacity',
    'Anaerobic',
)

# Upper boundaries as % of LTHR for zones 1–6; zone 7 is open-ended (Friel bike HR).
HR_ZONE_UPPER_PCTS = (81, 89, 93, 99, 102, 106)

ZONE_COLORS = (
    '#9CA3AF',  # Z1 gray
    '#3B82F6',  # Z2 blue
    '#22C55E',  # Z3 green
    '#EAB308',  # Z4 yellow
    '#F97316',  # Z5 orange
    '#EF4444',  # Z6 red
    '#A855F7',  # Z7 purple
)


def estimate_lthr(max_hr: int) -> int:
    # Half-up rounding (avoid banker's round(x.5)->even).
    return max(1, int(max_hr * 0.95 + 0.5))


def _pct_bounds(anchor: int, upper_pcts: tuple[int, ...]) -> list[tuple[int, Optional[int]]]:
    """Return (min, max) absolute bounds; last zone has max=None."""
    bounds: list[tuple[int, Optional[int]]] = []
    prev = 0
    for pct in upper_pcts:
        upper = max(prev, int(anchor * pct / 100 + 0.5))
        bounds.append((prev, upper))
        prev = upper + 1 if upper >= prev else prev + 1
    bounds.append((prev, None))
    return bounds


def default_power_zones(ftp: int) -> list[dict[str, Any]]:
    if ftp <= 0:
        raise ValueError('FTP must be positive')
    bounds = _pct_bounds(ftp, POWER_ZONE_UPPER_PCTS)
    return [
        {'name': POWER_ZONE_NAMES[i], 'min': lo, 'max': hi}
        for i, (lo, hi) in enumerate(bounds)
    ]


def default_hr_zones(max_hr: int) -> list[dict[str, Any]]:
    if max_hr <= 0:
        raise ValueError('max_hr must be positive')
    lthr = estimate_lthr(max_hr)
    bounds = _pct_bounds(lthr, HR_ZONE_UPPER_PCTS)
    return [
        {'name': HR_ZONE_NAMES[i], 'min': lo, 'max': hi}
        for i, (lo, hi) in enumerate(bounds)
    ]


def normalize_zones(raw: Any, *, names: tuple[str, ...] = POWER_ZONE_NAMES) -> Optional[list[dict[str, Any]]]:
    """Validate and normalize a 7-zone list. Returns None if invalid/empty."""
    if not raw:
        return None
    if not isinstance(raw, (list, tuple)) or len(raw) != 7:
        return None
    zones: list[dict[str, Any]] = []
    for i, item in enumerate(raw):
        if not isinstance(item, dict):
            return None
        try:
            lo = int(item['min'])
        except (KeyError, TypeError, ValueError):
            return None
        raw_max = item.get('max')
        if raw_max is None or raw_max == '':
            hi: Optional[int] = None
        else:
            try:
                hi = int(raw_max)
            except (TypeError, ValueError):
                return None
        if lo < 0:
            return None
        if hi is not None and hi < lo:
            return None
        if i < 6 and hi is None:
            return None
        name = (item.get('name') or names[i]).strip() or names[i]
        zones.append({'name': name, 'min': lo, 'max': hi})
    return zones


def zone_index(value: Optional[float], zones: list[dict[str, Any]]) -> Optional[int]:
    """Return 0-based zone index for a metric value, or None if unknown."""
    if value is None or not zones:
        return None
    try:
        v = float(value)
    except (TypeError, ValueError):
        return None
    for i, zone in enumerate(zones):
        lo = zone.get('min', 0)
        hi = zone.get('max')
        if v < lo:
            continue
        if hi is None or v <= hi:
            return i
    # Above last closed upper bound → last zone
    return len(zones) - 1


def resolve_power_zones(profile) -> Optional[list[dict[str, Any]]]:
    zones = normalize_zones(getattr(profile, 'power_zones', None), names=POWER_ZONE_NAMES)
    if zones:
        return zones
    ftp = getattr(profile, 'ftp', None)
    if ftp:
        return default_power_zones(int(ftp))
    return None


def resolve_hr_zones(profile) -> Optional[list[dict[str, Any]]]:
    zones = normalize_zones(getattr(profile, 'hr_zones', None), names=HR_ZONE_NAMES)
    if zones:
        return zones
    max_hr = getattr(profile, 'max_heart_rate', None)
    if max_hr:
        return default_hr_zones(int(max_hr))
    return None
