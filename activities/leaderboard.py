from datetime import date as date_cls, datetime, timedelta
from decimal import Decimal
from typing import List, Optional, Union
from zoneinfo import ZoneInfo

from django.conf import settings
from django.db.models import Sum
from django.utils import timezone

from activities.models import Activity
from profiles.models import Profile

VALID_METRICS = frozenset({'distance', 'duration'})
VALID_WEEKS = frozenset({'current', 'previous'})

_MONTHS_RU = (
    '', 'янв', 'фев', 'мар', 'апр', 'май', 'июн',
    'июл', 'авг', 'сен', 'окт', 'ноя', 'дек',
)


def _tz():
    return ZoneInfo(settings.TIME_ZONE)


def week_bounds(week: str = 'current', today: Optional[Union[date_cls, datetime]] = None):
    """Return [start, end) datetimes for Monday–Sunday week in project TZ."""
    if week not in VALID_WEEKS:
        raise ValueError(f'Invalid week: {week}')

    tz = _tz()
    if today is None:
        today = timezone.now().astimezone(tz).date()
    elif isinstance(today, datetime):
        today = today.astimezone(tz).date()

    monday = today - timedelta(days=today.weekday())
    if week == 'previous':
        monday = monday - timedelta(days=7)
    sunday_end = monday + timedelta(days=7)

    start = timezone.make_aware(datetime.combine(monday, datetime.min.time()), tz)
    end = timezone.make_aware(datetime.combine(sunday_end, datetime.min.time()), tz)
    return start, end


def week_label(start, end) -> str:
    """Human-readable range like «29 сен – 5 окт»."""
    last_day = (end - timedelta(seconds=1)).astimezone(_tz()).date()
    start_local = start.astimezone(_tz()).date()
    if start_local.month == last_day.month:
        return f'{start_local.day}–{last_day.day} {_MONTHS_RU[last_day.month]}'
    return (
        f'{start_local.day} {_MONTHS_RU[start_local.month]} – '
        f'{last_day.day} {_MONTHS_RU[last_day.month]}'
    )


def _format_duration(total_seconds) -> str:
    total = int(total_seconds or 0)
    hours, rem = divmod(total, 3600)
    minutes, seconds = divmod(rem, 60)
    if hours:
        return f'{hours}:{minutes:02d}:{seconds:02d}'
    return f'{minutes}:{seconds:02d}'


def _format_distance(km) -> str:
    value = Decimal(km or 0).quantize(Decimal('0.01'))
    text = f'{value:f}'.rstrip('0').rstrip('.')
    return f'{text} км'


def weekly_leaders(
    viewer: Profile,
    *,
    sport_id: Optional[int] = None,
    metric: str = 'distance',
    week: str = 'current',
    limit: int = 10,
    today=None,
) -> dict:
    """Aggregate weekly ranking for viewer + follows."""
    if metric not in VALID_METRICS:
        raise ValueError(f'Invalid metric: {metric}')

    start, end = week_bounds(week, today=today)
    follow_ids = list(viewer.follows.values_list('pk', flat=True))
    profile_ids = [viewer.pk, *follow_ids]

    qs = Activity.objects.filter(
        profile_id__in=profile_ids,
        started_at__gte=start,
        started_at__lt=end,
    )
    if sport_id is not None:
        qs = qs.filter(activity_type_id=sport_id)

    if metric == 'distance':
        rows = (
            qs.values('profile_id')
            .annotate(total=Sum('distance'))
            .order_by('-total')[:limit]
        )
    else:
        rows = (
            qs.values('profile_id')
            .annotate(total=Sum('duration'))
            .order_by('-total')[:limit]
        )

    rows = list(rows)
    profiles = {
        p.pk: p
        for p in Profile.objects.filter(pk__in=[r['profile_id'] for r in rows])
    }

    leaders: List[dict] = []
    for rank, row in enumerate(rows, start=1):
        profile = profiles.get(row['profile_id'])
        if profile is None:
            continue
        total = row['total']
        if metric == 'distance':
            total = total or Decimal('0')
            total_display = _format_distance(total)
            total_value = float(total)
        else:
            total_seconds = int(total.total_seconds()) if total else 0
            total_display = _format_duration(total_seconds)
            total_value = total_seconds

        photo_url = profile.photo.url if profile.photo else None
        leaders.append({
            'rank': rank,
            'profile_id': profile.pk,
            'display_name': profile.display_name,
            'photo_url': photo_url,
            'initial': (profile.email[:1] or '?').upper(),
            'total': total_value,
            'total_display': total_display,
        })

    return {
        'week': week,
        'week_label': week_label(start, end),
        'week_start': start.isoformat(),
        'week_end': end.isoformat(),
        'metric': metric,
        'sport': sport_id,
        'leaders': leaders,
    }
