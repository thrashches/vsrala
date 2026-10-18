"""Generate static map preview PNGs from activity track points."""

from __future__ import annotations

import logging
import math
import time
from io import BytesIO
from typing import Optional

import requests
from django.core.files.base import ContentFile
from PIL import Image, ImageDraw

logger = logging.getLogger(__name__)

IMG_WIDTH = 960
IMG_HEIGHT = 416
TILE_SIZE = 256
MAX_ZOOM = 18
MIN_ZOOM = 1
# Track bounding box must fit within these fractions of the image.
MAX_TRACK_HEIGHT_RATIO = 0.5
MAX_TRACK_WIDTH_RATIO = 0.9
BG = (249, 250, 251)
LINE_COLOR = (252, 82, 0)  # #FC5200
LINE_WIDTH = 4
START_FILL = (34, 197, 94)
END_FILL = (239, 68, 68)
MARKER_R = 7

TILE_URL = 'https://tile.openstreetmap.org/{z}/{x}/{y}.png'
TILE_HEADERS = {
    'User-Agent': 'vsrala/1.0 (activity map preview; https://github.com/null0ff/vsrala)',
    'Referer': 'https://vsrala.local/',
}
TILE_TIMEOUT = 8
TILE_RETRIES = 3
TILE_RETRY_BACKOFF = 0.4
TILE_REQUEST_INTERVAL = 0.15
TILE_MISSING_RETRY_DELAY = 0.5

# Process-wide tile cache to speed up batch regeneration (successful tiles only).
_TILE_CACHE: dict[tuple[int, int, int], Image.Image] = {}
_TILE_CACHE_MAX = 512
_TILE_SESSION: Optional[requests.Session] = None
_LAST_TILE_REQUEST_AT = 0.0


def _tile_session() -> requests.Session:
    global _TILE_SESSION
    if _TILE_SESSION is None:
        _TILE_SESSION = requests.Session()
        _TILE_SESSION.headers.update(TILE_HEADERS)
    return _TILE_SESSION


def _throttle_tile_request() -> None:
    global _LAST_TILE_REQUEST_AT
    now = time.monotonic()
    wait = TILE_REQUEST_INTERVAL - (now - _LAST_TILE_REQUEST_AT)
    if wait > 0:
        time.sleep(wait)
    _LAST_TILE_REQUEST_AT = time.monotonic()


def _cache_successful_tile(key: tuple[int, int, int], tile: Image.Image) -> None:
    if len(_TILE_CACHE) >= _TILE_CACHE_MAX and key not in _TILE_CACHE:
        # Drop an arbitrary old entry (FIFO-ish via dict order).
        _TILE_CACHE.pop(next(iter(_TILE_CACHE)))
    _TILE_CACHE[key] = tile


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
        out.append((lat, lon))
    return out


def _lon_to_world_x(lon: float, zoom: int) -> float:
    n = 2 ** zoom
    return (lon + 180.0) / 360.0 * n * TILE_SIZE


def _lat_to_world_y(lat: float, zoom: int) -> float:
    lat = max(min(lat, 85.05112878), -85.05112878)
    lat_rad = math.radians(lat)
    n = 2 ** zoom
    return (1.0 - math.log(math.tan(lat_rad) + 1.0 / math.cos(lat_rad)) / math.pi) / 2.0 * n * TILE_SIZE


def _track_span_px(
    min_lat: float, max_lat: float, min_lon: float, max_lon: float, zoom: int,
) -> tuple[float, float, float, float]:
    xs = [_lon_to_world_x(min_lon, zoom), _lon_to_world_x(max_lon, zoom)]
    ys = [_lat_to_world_y(min_lat, zoom), _lat_to_world_y(max_lat, zoom)]
    min_x, max_x = min(xs), max(xs)
    min_y, max_y = min(ys), max(ys)
    # Avoid zero-size bbox (stationary / tiny GPS noise).
    if max_x - min_x < 2:
        mid = (min_x + max_x) / 2
        min_x, max_x = mid - 1, mid + 1
    if max_y - min_y < 2:
        mid = (min_y + max_y) / 2
        min_y, max_y = mid - 1, mid + 1
    return min_x, max_x, min_y, max_y


def _choose_zoom(min_lat: float, max_lat: float, min_lon: float, max_lon: float) -> int:
    """Highest zoom where the track fits within height/width ratios."""
    max_h = IMG_HEIGHT * MAX_TRACK_HEIGHT_RATIO
    max_w = IMG_WIDTH * MAX_TRACK_WIDTH_RATIO
    chosen = MIN_ZOOM
    for z in range(MIN_ZOOM, MAX_ZOOM + 1):
        min_x, max_x, min_y, max_y = _track_span_px(min_lat, max_lat, min_lon, max_lon, z)
        w = max_x - min_x
        h = max_y - min_y
        if h <= max_h and w <= max_w:
            chosen = z
        else:
            break
    return chosen


def _is_retryable_http_error(exc: BaseException) -> bool:
    if isinstance(exc, (requests.Timeout, requests.ConnectionError)):
        return True
    if isinstance(exc, requests.HTTPError) and exc.response is not None:
        status = exc.response.status_code
        return status == 429 or status >= 500
    return False


def _download_tile(url: str) -> Image.Image:
    _throttle_tile_request()
    resp = _tile_session().get(url, timeout=TILE_TIMEOUT)
    resp.raise_for_status()
    return Image.open(BytesIO(resp.content)).convert('RGB')


def _fetch_tile(z: int, x: int, y: int, cache: dict) -> Optional[Image.Image]:
    key = (z, x, y)
    if key in cache:
        return cache[key]
    if key in _TILE_CACHE:
        tile = _TILE_CACHE[key]
        cache[key] = tile
        return tile
    n = 2 ** z
    if x < 0 or y < 0 or x >= n or y >= n:
        # Permanent miss for this compose; do not hit the network again.
        cache[key] = None
        return None

    url = TILE_URL.format(z=z, x=x, y=y)
    last_exc: Optional[BaseException] = None
    for attempt in range(TILE_RETRIES):
        try:
            tile = _download_tile(url)
            cache[key] = tile
            _cache_successful_tile(key, tile)
            return tile
        except requests.HTTPError as exc:
            last_exc = exc
            if not _is_retryable_http_error(exc) or attempt + 1 >= TILE_RETRIES:
                break
            time.sleep(TILE_RETRY_BACKOFF * (2 ** attempt))
        except (requests.Timeout, requests.ConnectionError) as exc:
            last_exc = exc
            if attempt + 1 >= TILE_RETRIES:
                break
            time.sleep(TILE_RETRY_BACKOFF * (2 ** attempt))
        except Exception as exc:
            last_exc = exc
            break

    logger.warning('Failed to fetch map tile %s', url, exc_info=last_exc)
    return None


def _paste_tile(
    img: Image.Image, tile: Image.Image, tx: int, ty: int, left: float, top: float,
) -> None:
    px = int(tx * TILE_SIZE - left)
    py = int(ty * TILE_SIZE - top)
    img.paste(tile, (px, py))


def _compose_basemap(
    left: float, top: float, zoom: int, *, use_tiles: bool,
) -> Image.Image:
    img = Image.new('RGB', (IMG_WIDTH, IMG_HEIGHT), BG)
    if not use_tiles:
        return img

    local_cache: dict = {}
    x0 = int(math.floor(left / TILE_SIZE))
    y0 = int(math.floor(top / TILE_SIZE))
    x1 = int(math.floor((left + IMG_WIDTH) / TILE_SIZE))
    y1 = int(math.floor((top + IMG_HEIGHT) / TILE_SIZE))

    n = 2 ** zoom
    missing: list[tuple[int, int]] = []
    for ty in range(y0, y1 + 1):
        for tx in range(x0, x1 + 1):
            tile = _fetch_tile(zoom, tx, ty, local_cache)
            if tile is None:
                if 0 <= tx < n and 0 <= ty < n:
                    missing.append((tx, ty))
                continue
            _paste_tile(img, tile, tx, ty, left, top)

    if missing:
        time.sleep(TILE_MISSING_RETRY_DELAY)
        still_missing: list[tuple[int, int]] = []
        for tx, ty in missing:
            # Network failures are not cached; OOB misses stay None in local_cache.
            tile = _fetch_tile(zoom, tx, ty, local_cache)
            if tile is None:
                still_missing.append((tx, ty))
                continue
            _paste_tile(img, tile, tx, ty, left, top)
        if still_missing:
            logger.warning(
                'Map preview basemap incomplete: %d/%d tiles missing at z=%d',
                len(still_missing),
                (x1 - x0 + 1) * (y1 - y0 + 1),
                zoom,
            )
    return img


def render_map_preview_image(
    track_points: list,
    *,
    use_tiles: bool = True,
) -> Optional[Image.Image]:
    """
    Draw an orange polyline over an OSM tile basemap.
    Track bounding box height is at most 50% of the image height.
    """
    pts = _extract_latlngs(track_points)
    if len(pts) < 2:
        return None

    lats = [p[0] for p in pts]
    lons = [p[1] for p in pts]
    min_lat, max_lat = min(lats), max(lats)
    min_lon, max_lon = min(lons), max(lons)

    zoom = _choose_zoom(min_lat, max_lat, min_lon, max_lon)
    min_x, max_x, min_y, max_y = _track_span_px(min_lat, max_lat, min_lon, max_lon, zoom)
    center_x = (min_x + max_x) / 2.0
    center_y = (min_y + max_y) / 2.0
    left = center_x - IMG_WIDTH / 2.0
    top = center_y - IMG_HEIGHT / 2.0

    img = _compose_basemap(left, top, zoom, use_tiles=use_tiles)
    draw = ImageDraw.Draw(img)

    xy = [
        (_lon_to_world_x(lon, zoom) - left, _lat_to_world_y(lat, zoom) - top)
        for lat, lon in pts
    ]
    draw.line(xy, fill=LINE_COLOR, width=LINE_WIDTH, joint='curve')

    sx, sy = xy[0]
    ex, ey = xy[-1]
    draw.ellipse(
        [sx - MARKER_R, sy - MARKER_R, sx + MARKER_R, sy + MARKER_R],
        fill=START_FILL,
        outline=(255, 255, 255),
        width=2,
    )
    draw.ellipse(
        [ex - MARKER_R, ey - MARKER_R, ex + MARKER_R, ey + MARKER_R],
        fill=END_FILL,
        outline=(255, 255, 255),
        width=2,
    )
    return img


def build_map_preview_for_activity(activity) -> Optional[ContentFile]:
    img = render_map_preview_image(activity.track_points or [])
    if img is None:
        return None
    buf = BytesIO()
    img.save(buf, format='PNG', optimize=True)
    return ContentFile(buf.getvalue(), name='map_preview.png')


def apply_map_preview(activity, *, save: bool = True) -> bool:
    """Generate and attach map_preview on activity. Returns True if image set."""
    content = build_map_preview_for_activity(activity)
    old_name = activity.map_preview.name if activity.map_preview else ''

    if content is None:
        if activity.map_preview:
            activity.map_preview.delete(save=False)
        if save and activity.pk:
            activity.save(update_fields=['map_preview'])
        return False

    if old_name:
        activity.map_preview.delete(save=False)
    activity.map_preview.save('map_preview.png', content, save=False)
    if save and activity.pk:
        activity.save(update_fields=['map_preview'])
    return True
