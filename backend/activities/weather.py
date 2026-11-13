"""Fetch and attach Open-Meteo hourly weather to outdoor activities."""

from __future__ import annotations

import logging
import math
import time
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any, Optional

import requests
from django.utils.dateparse import parse_datetime

from activities.models import Activity, WeatherForecast
from routes.models import haversine_m

logger = logging.getLogger(__name__)

REUSE_RADIUS_M = 20_000.0
LONG_ROUTE_SPAN_M = 100_000.0
PRECIP_PRIORITY_MM = 0.5
HTTP_TIMEOUT = 12
HTTP_RETRIES = 3
HTTP_RETRY_BACKOFF = 0.4
FORECAST_PAST_DAYS_LIMIT = 5  # Open-Meteo forecast past_days max is typically 92; use archive beyond recent

FORECAST_URL = 'https://api.open-meteo.com/v1/forecast'
ARCHIVE_URL = 'https://archive-api.open-meteo.com/v1/archive'
HOURLY_VARS = (
    'temperature_2m',
    'precipitation',
    'cloud_cover',
    'wind_speed_10m',
    'wind_direction_10m',
    'weather_code',
)

_SESSION: Optional[requests.Session] = None


def _session() -> requests.Session:
    global _SESSION
    if _SESSION is None:
        _SESSION = requests.Session()
        _SESSION.headers.update({
            'User-Agent': 'vsrala/1.0 (activity weather; https://github.com/null0ff/vsrala)',
        })
    return _SESSION


def _as_utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _extract_latlngs(track_points: list) -> list[tuple[float, float]]:
    out: list[tuple[float, float]] = []
    for p in track_points or []:
        if not p or len(p) < 2:
            continue
        try:
            lat = float(p[0])
            lon = float(p[1])
        except (TypeError, ValueError):
            continue
        if math.isnan(lat) or math.isnan(lon):
            continue
        if abs(lat) > 90 or abs(lon) > 180:
            continue
        out.append((lat, lon))
    return out


def track_bbox_center(points: list[tuple[float, float]]) -> Optional[tuple[float, float]]:
    if not points:
        return None
    lats = [p[0] for p in points]
    lons = [p[1] for p in points]
    return ((min(lats) + max(lats)) / 2.0, (min(lons) + max(lons)) / 2.0)


def request_points_for_track(track_points: list) -> list[tuple[float, float]]:
    """
    Default: bbox center. If start–finish > 100 km, also include start and finish.
    Deduplicate near-identical points.
    """
    coords = _extract_latlngs(track_points)
    if not coords:
        return []
    center = track_bbox_center(coords)
    assert center is not None
    start, finish = coords[0], coords[-1]
    span_m = haversine_m(start[0], start[1], finish[0], finish[1])
    points = [center]
    if span_m > LONG_ROUTE_SPAN_M:
        points.extend([start, finish])
    return _dedupe_points(points, min_distance_m=1000.0)


def _dedupe_points(
    points: list[tuple[float, float]], *, min_distance_m: float,
) -> list[tuple[float, float]]:
    out: list[tuple[float, float]] = []
    for p in points:
        if any(haversine_m(p[0], p[1], q[0], q[1]) < min_distance_m for q in out):
            continue
        out.append(p)
    return out


def weather_code_to_condition(code: Optional[int], *, precip_mm: float = 0.0) -> str:
    """Map WMO weather_code to clear/cloud/rain/snow."""
    if code is None:
        if precip_mm >= PRECIP_PRIORITY_MM:
            return 'rain'
        return 'cloud'
    code = int(code)
    # Snow / ice
    if code in (71, 73, 75, 77, 85, 86) or code in (66, 67):
        return 'snow'
    # Rain / drizzle / thunderstorm / showers
    if code in (51, 53, 55, 56, 57, 61, 63, 65, 80, 81, 82, 95, 96, 99):
        return 'rain'
    # Fog / deposit — treat as cloudy
    if code in (45, 48):
        return 'cloud'
    # Overcast / cloudy
    if code in (1, 2, 3):
        return 'cloud' if code >= 2 else 'clear'
    if code == 0:
        return 'clear'
    if precip_mm >= PRECIP_PRIORITY_MM:
        return 'rain'
    return 'cloud'


def find_nearby_forecast(
    lat: float,
    lon: float,
    period_start: datetime,
    period_end: datetime,
    *,
    radius_m: float = REUSE_RADIUS_M,
) -> Optional[WeatherForecast]:
    """Find closest OK forecast within radius covering the time window."""
    start = _as_utc(period_start)
    end = _as_utc(period_end)
    # Rough degree box (~1 deg lat ≈ 111 km) to limit candidates
    deg = (radius_m / 111_000.0) * 1.2
    candidates = WeatherForecast.objects.filter(
        status=WeatherForecast.STATUS_OK,
        lat__gte=Decimal(str(round(lat - deg, 6))),
        lat__lte=Decimal(str(round(lat + deg, 6))),
        lon__gte=Decimal(str(round(lon - deg, 6))),
        lon__lte=Decimal(str(round(lon + deg, 6))),
        period_start__lte=start,
        period_end__gte=end,
    )
    best: Optional[WeatherForecast] = None
    best_dist = radius_m + 1
    for fc in candidates.iterator():
        dist = haversine_m(lat, lon, float(fc.lat), float(fc.lon))
        if dist <= radius_m and dist < best_dist:
            best = fc
            best_dist = dist
    return best


def _parse_iso_hour(value: str) -> Optional[datetime]:
    if not value:
        return None
    # Open-Meteo returns "2024-01-01T12:00" without Z
    dt = parse_datetime(value)
    if dt is None:
        try:
            dt = datetime.fromisoformat(value)
        except ValueError:
            return None
    return _as_utc(dt)


def _normalize_hourly(payload: dict) -> list[dict[str, Any]]:
    hourly = payload.get('hourly') or {}
    times = hourly.get('time') or []
    temps = hourly.get('temperature_2m') or []
    precips = hourly.get('precipitation') or []
    clouds = hourly.get('cloud_cover') or []
    winds = hourly.get('wind_speed_10m') or []
    dirs = hourly.get('wind_direction_10m') or []
    codes = hourly.get('weather_code') or []
    rows: list[dict[str, Any]] = []
    for i, t in enumerate(times):
        dt = _parse_iso_hour(t)
        if dt is None:
            continue
        code = codes[i] if i < len(codes) else None
        rows.append({
            'time': dt.isoformat().replace('+00:00', 'Z'),
            'temperature_c': temps[i] if i < len(temps) else None,
            'precipitation_mm': precips[i] if i < len(precips) else None,
            'cloud_cover_pct': clouds[i] if i < len(clouds) else None,
            'wind_speed_kmh': winds[i] if i < len(winds) else None,
            'wind_direction_deg': dirs[i] if i < len(dirs) else None,
            'weather_code': int(code) if code is not None else None,
        })
    return rows


def _http_get(url: str, params: dict) -> dict:
    last_exc: Optional[BaseException] = None
    for attempt in range(HTTP_RETRIES):
        try:
            resp = _session().get(url, params=params, timeout=HTTP_TIMEOUT)
            resp.raise_for_status()
            return resp.json()
        except (requests.Timeout, requests.ConnectionError, requests.HTTPError) as exc:
            last_exc = exc
            if isinstance(exc, requests.HTTPError) and exc.response is not None:
                if exc.response.status_code < 500 and exc.response.status_code != 429:
                    raise
            if attempt + 1 >= HTTP_RETRIES:
                break
            time.sleep(HTTP_RETRY_BACKOFF * (2 ** attempt))
    assert last_exc is not None
    raise last_exc


def fetch_open_meteo_hourly(
    lat: float,
    lon: float,
    period_start: datetime,
    period_end: datetime,
) -> list[dict[str, Any]]:
    """Fetch hourly weather; choose forecast vs archive by age."""
    start = _as_utc(period_start).replace(minute=0, second=0, microsecond=0)
    end = _as_utc(period_end)
    # Include full end hour
    if end.minute or end.second or end.microsecond:
        end = end.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)
    else:
        end = end.replace(minute=0, second=0, microsecond=0)
    if end < start:
        end = start

    now = datetime.now(timezone.utc)
    age_days = (now.date() - start.date()).days
    start_date = start.date().isoformat()
    end_date = end.date().isoformat()
    common = {
        'latitude': round(lat, 6),
        'longitude': round(lon, 6),
        'hourly': ','.join(HOURLY_VARS),
        'timezone': 'UTC',
        'wind_speed_unit': 'kmh',
    }

    if age_days <= FORECAST_PAST_DAYS_LIMIT and start <= now + timedelta(days=1):
        params = {
            **common,
            'start_date': start_date,
            'end_date': end_date,
        }
        # Forecast API also accepts start_date/end_date for recent ranges
        try:
            payload = _http_get(FORECAST_URL, params)
        except Exception:
            payload = _http_get(ARCHIVE_URL, {
                **common,
                'start_date': start_date,
                'end_date': end_date,
            })
    else:
        payload = _http_get(ARCHIVE_URL, {
            **common,
            'start_date': start_date,
            'end_date': end_date,
        })

    rows = _normalize_hourly(payload)
    # Clip to requested window (inclusive of hour containing end)
    clipped = []
    for row in rows:
        dt = _parse_iso_hour(row['time'])
        if dt is None:
            continue
        if start <= dt <= end:
            clipped.append(row)
    return clipped


def get_or_fetch_forecast(
    lat: float,
    lon: float,
    period_start: datetime,
    period_end: datetime,
) -> Optional[WeatherForecast]:
    existing = find_nearby_forecast(lat, lon, period_start, period_end)
    if existing is not None:
        return existing

    start = _as_utc(period_start).replace(minute=0, second=0, microsecond=0)
    end = _as_utc(period_end)
    if end.minute or end.second or end.microsecond:
        end = end.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)
    else:
        end = max(end, start)

    try:
        hourly = fetch_open_meteo_hourly(lat, lon, start, end)
    except Exception as exc:
        logger.warning(
            'Open-Meteo fetch failed for %.4f,%.4f: %s', lat, lon, exc,
        )
        WeatherForecast.objects.create(
            lat=Decimal(str(round(lat, 6))),
            lon=Decimal(str(round(lon, 6))),
            period_start=start,
            period_end=end,
            hourly=[],
            status=WeatherForecast.STATUS_ERROR,
            error=str(exc)[:2000],
        )
        return None

    if not hourly:
        logger.warning('Open-Meteo returned no hourly data for %.4f,%.4f', lat, lon)
        return None

    period_end_stored = _parse_iso_hour(hourly[-1]['time']) or end
    return WeatherForecast.objects.create(
        lat=Decimal(str(round(lat, 6))),
        lon=Decimal(str(round(lon, 6))),
        period_start=start,
        period_end=period_end_stored,
        hourly=hourly,
        status=WeatherForecast.STATUS_OK,
    )


def _hour_at_elapsed(
    points: list,
    elapsed_sec: float,
) -> Optional[tuple[float, float]]:
    """Interpolate / pick track lat/lon nearest to elapsed seconds."""
    coords_with_t: list[tuple[float, float, float]] = []
    for p in points or []:
        if not p or len(p) < 2:
            continue
        try:
            lat, lon = float(p[0]), float(p[1])
            t = float(p[2]) if len(p) >= 3 and p[2] is not None else None
        except (TypeError, ValueError):
            continue
        if t is None:
            continue
        coords_with_t.append((lat, lon, t))
    if not coords_with_t:
        coords = _extract_latlngs(points)
        if not coords:
            return None
        # No timestamps: approximate by index fraction
        return None
    # Nearest by time
    best = min(coords_with_t, key=lambda x: abs(x[2] - elapsed_sec))
    return best[0], best[1]


def _pick_forecast_for_point(
    forecasts: list[WeatherForecast],
    lat: float,
    lon: float,
) -> Optional[WeatherForecast]:
    if not forecasts:
        return None
    return min(
        forecasts,
        key=lambda fc: haversine_m(lat, lon, float(fc.lat), float(fc.lon)),
    )


def _hourly_row_at(forecast: WeatherForecast, when: datetime) -> Optional[dict]:
    target = _as_utc(when).replace(minute=0, second=0, microsecond=0)
    best = None
    best_delta = None
    for row in forecast.hourly or []:
        dt = _parse_iso_hour(row.get('time') or '')
        if dt is None:
            continue
        delta = abs((dt - target).total_seconds())
        if best_delta is None or delta < best_delta:
            best = row
            best_delta = delta
    if best is None or (best_delta is not None and best_delta > 3600 * 2):
        return None
    return best


def build_weather_timeline(
    activity: Activity,
    forecasts: list[WeatherForecast],
) -> list[dict[str, Any]]:
    if not forecasts:
        return []
    start = _as_utc(activity.started_at)
    duration = activity.duration or timedelta(0)
    end = start + duration
    # Hour buckets from start hour through end hour
    cursor = start.replace(minute=0, second=0, microsecond=0)
    timeline: list[dict[str, Any]] = []
    points = activity.track_points or []
    center = track_bbox_center(_extract_latlngs(points))

    while cursor <= end:
        elapsed = max(0.0, (cursor - start).total_seconds())
        loc = _hour_at_elapsed(points, elapsed)
        if loc is None:
            loc = center
        if loc is None:
            cursor += timedelta(hours=1)
            continue
        fc = _pick_forecast_for_point(forecasts, loc[0], loc[1])
        if fc is None:
            cursor += timedelta(hours=1)
            continue
        row = _hourly_row_at(fc, cursor)
        if row is None:
            cursor += timedelta(hours=1)
            continue
        precip = float(row['precipitation_mm'] or 0)
        timeline.append({
            'time': cursor.isoformat().replace('+00:00', 'Z'),
            'temperature_c': row.get('temperature_c'),
            'precipitation_mm': row.get('precipitation_mm'),
            'cloud_cover_pct': row.get('cloud_cover_pct'),
            'wind_speed_kmh': row.get('wind_speed_kmh'),
            'wind_direction_deg': row.get('wind_direction_deg'),
            'weather_code': row.get('weather_code'),
            'condition': weather_code_to_condition(row.get('weather_code'), precip_mm=precip),
            'lat': round(loc[0], 6),
            'lon': round(loc[1], 6),
        })
        cursor += timedelta(hours=1)
    return timeline


def build_weather_summary(timeline: list[dict[str, Any]]) -> Optional[dict[str, Any]]:
    if not timeline:
        return None
    mid = timeline[len(timeline) // 2]
    total_precip = sum(float(r.get('precipitation_mm') or 0) for r in timeline)
    codes = [r.get('weather_code') for r in timeline if r.get('weather_code') is not None]
    precip_condition = None
    if total_precip >= PRECIP_PRIORITY_MM:
        # Prefer snow if any snow codes present
        if any(weather_code_to_condition(c) == 'snow' for c in codes):
            precip_condition = 'snow'
        else:
            precip_condition = 'rain'
    elif any(weather_code_to_condition(c) in ('rain', 'snow') for c in codes):
        # Weather codes indicate precip even if amounts small
        if any(weather_code_to_condition(c) == 'snow' for c in codes):
            precip_condition = 'snow'
        else:
            precip_condition = 'rain'

    condition = precip_condition or mid.get('condition') or weather_code_to_condition(
        mid.get('weather_code'),
        precip_mm=float(mid.get('precipitation_mm') or 0),
    )
    return {
        'condition': condition,
        'temperature_c': mid.get('temperature_c'),
        'wind_speed_kmh': mid.get('wind_speed_kmh'),
        'wind_direction_deg': mid.get('wind_direction_deg'),
        'precipitation_mm': round(total_precip, 2),
    }


def attach_weather(activity: Activity) -> bool:
    """
    Resolve/fetch forecasts for activity GPS zones and store timeline + summary.
    Returns True if weather_summary was set.
    """
    if activity.is_indoor:
        return False
    points = activity.track_points or []
    request_pts = request_points_for_track(points)
    if not request_pts:
        return False
    if not activity.started_at:
        return False

    start = _as_utc(activity.started_at)
    end = start + (activity.duration or timedelta(0))
    forecasts: list[WeatherForecast] = []
    for lat, lon in request_pts:
        fc = get_or_fetch_forecast(lat, lon, start, end)
        if fc is not None and fc.status == WeatherForecast.STATUS_OK:
            forecasts.append(fc)

    # Deduplicate by pk
    unique: dict[int, WeatherForecast] = {fc.pk: fc for fc in forecasts}
    forecasts = list(unique.values())

    timeline = build_weather_timeline(activity, forecasts)
    summary = build_weather_summary(timeline)

    activity.weather_timeline = timeline
    activity.weather_summary = summary
    activity.save(update_fields=['weather_timeline', 'weather_summary'])
    if forecasts:
        activity.weather_forecasts.set(forecasts)
    else:
        activity.weather_forecasts.clear()
    return summary is not None
