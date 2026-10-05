"""Generate zone-colored stream timeline PNGs for activities."""

from __future__ import annotations

from io import BytesIO
from typing import Any, Optional

from django.core.files.base import ContentFile
from PIL import Image, ImageDraw, ImageFont

from profiles.zones import ZONE_COLORS, resolve_hr_zones, resolve_power_zones, zone_index

BAR_COUNT = 320
IMG_WIDTH = 960
IMG_HEIGHT = 160
BAR_TOP = 28
BAR_BOTTOM = 120
LEGEND_Y = 136
BG = (249, 250, 251)
GAP = 1


def _stream_has_data(values: Any) -> bool:
    if not values:
        return False
    return any(v is not None for v in values)


def _downsample(values: list, times: list, n: int) -> list[Optional[float]]:
    """Average values into n time buckets across the activity duration."""
    if not values:
        return []
    length = len(values)
    if times and len(times) == length:
        t_max = max(t for t in times if t is not None) if any(t is not None for t in times) else length - 1
        t_max = max(float(t_max), 1.0)
        buckets: list[list[float]] = [[] for _ in range(n)]
        for i, v in enumerate(values):
            if v is None:
                continue
            t = times[i] if times[i] is not None else (i / max(length - 1, 1)) * t_max
            idx = min(n - 1, int(float(t) / t_max * n))
            buckets[idx].append(float(v))
        return [sum(b) / len(b) if b else None for b in buckets]

    # Index-based fallback
    out: list[Optional[float]] = []
    for i in range(n):
        start = int(i * length / n)
        end = max(start + 1, int((i + 1) * length / n))
        chunk = [float(v) for v in values[start:end] if v is not None]
        out.append(sum(chunk) / len(chunk) if chunk else None)
    return out


def _font(size: int = 12):
    try:
        return ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf', size)
    except OSError:
        try:
            return ImageFont.truetype('/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf', size)
        except OSError:
            return ImageFont.load_default()


def _hex_to_rgb(color: str) -> tuple[int, int, int]:
    c = color.lstrip('#')
    return int(c[0:2], 16), int(c[2:4], 16), int(c[4:6], 16)


def render_zone_timeline_image(
    values: list[Optional[float]],
    zones: list[dict[str, Any]],
    *,
    label: str,
) -> Image.Image:
    img = Image.new('RGB', (IMG_WIDTH, IMG_HEIGHT), BG)
    draw = ImageDraw.Draw(img)
    font = _font(12)
    font_sm = _font(10)

    draw.text((12, 8), label, fill=(55, 65, 81), font=font)

    n = len(values)
    if n == 0:
        return img

    usable = IMG_WIDTH - 24
    bar_w = max(1, (usable - GAP * (n - 1)) // n)
    total_w = n * bar_w + (n - 1) * GAP
    x0 = 12 + max(0, (usable - total_w) // 2)

    finite = [v for v in values if v is not None]
    vmax = max(finite) if finite else 1.0
    vmin = 0.0
    span = max(vmax - vmin, 1.0)
    bar_h = BAR_BOTTOM - BAR_TOP

    for i, v in enumerate(values):
        x = x0 + i * (bar_w + GAP)
        if v is None:
            color = (229, 231, 235)
            h = max(2, int(bar_h * 0.08))
        else:
            zi = zone_index(v, zones)
            color = _hex_to_rgb(ZONE_COLORS[zi if zi is not None else 0])
            h = max(3, int(bar_h * ((v - vmin) / span)))
        y = BAR_BOTTOM - h
        draw.rectangle([x, y, x + bar_w - 1, BAR_BOTTOM], fill=color)

    # Legend
    lx = 12
    for i, zone in enumerate(zones[:7]):
        color = _hex_to_rgb(ZONE_COLORS[i])
        draw.rectangle([lx, LEGEND_Y, lx + 8, LEGEND_Y + 8], fill=color)
        name = f'Z{i + 1}'
        draw.text((lx + 11, LEGEND_Y - 1), name, fill=(107, 114, 128), font=font_sm)
        lx += 44

    return img


def build_zone_timeline_for_activity(activity) -> tuple[Optional[ContentFile], str]:
    """
    Build a zone timeline image for the activity.
    Returns (ContentFile or None, stream_key).
    Prefers power over heart rate.
    """
    streams = activity.streams or {}
    times = streams.get('time') or []
    profile = activity.profile

    power = streams.get('power') or []
    hr = streams.get('hr') or []

    if _stream_has_data(power):
        zones = resolve_power_zones(profile)
        if zones:
            buckets = _downsample(power, times, BAR_COUNT)
            img = render_zone_timeline_image(buckets, zones, label='Мощность · зоны')
            buf = BytesIO()
            img.save(buf, format='PNG', optimize=True)
            return ContentFile(buf.getvalue(), name='zone_timeline.png'), 'power'

    if _stream_has_data(hr):
        zones = resolve_hr_zones(profile)
        if zones:
            buckets = _downsample(hr, times, BAR_COUNT)
            img = render_zone_timeline_image(buckets, zones, label='Пульс · зоны')
            buf = BytesIO()
            img.save(buf, format='PNG', optimize=True)
            return ContentFile(buf.getvalue(), name='zone_timeline.png'), 'hr'

    return None, ''


def apply_zone_timeline(activity, *, save: bool = True) -> bool:
    """Generate and attach zone_timeline on activity. Returns True if image set."""
    content, stream_key = build_zone_timeline_for_activity(activity)
    old_name = activity.zone_timeline.name if activity.zone_timeline else ''

    if content is None:
        if activity.zone_timeline:
            activity.zone_timeline.delete(save=False)
        activity.zone_stream = ''
        if save and activity.pk:
            activity.save(update_fields=['zone_timeline', 'zone_stream'])
        return False

    if old_name:
        activity.zone_timeline.delete(save=False)
    activity.zone_timeline.save('zone_timeline.png', content, save=False)
    activity.zone_stream = stream_key
    if save and activity.pk:
        activity.save(update_fields=['zone_timeline', 'zone_stream'])
    return True
