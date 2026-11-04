from __future__ import annotations

from datetime import date as date_cls, datetime, timedelta
from decimal import Decimal
from typing import Optional, Union

from django.db.models import Avg, Count, Sum, Value
from django.db.models.functions import Coalesce
from django.utils import timezone

from activities.activity_types import PACE_SPORT_SLUGS
from activities.leaderboard import _format_distance, _format_duration
from activities.year_stats import available_years, year_bounds


def _format_elevation(meters) -> str:
    value = Decimal(meters or 0).quantize(Decimal('0.1'))
    text = f'{value:f}'.rstrip('0').rstrip('.')
    return f'{text} м'


def _format_number(value, places: str = '0.01') -> str:
    dec = Decimal(value or 0).quantize(Decimal(places))
    return f'{dec:f}'.rstrip('0').rstrip('.')


def _format_speed(kmh) -> str:
    if kmh is None:
        return ''
    return f'{_format_number(kmh)} км/ч'


def _format_pace(min_per_km) -> str:
    if min_per_km is None or min_per_km <= 0:
        return ''
    total_sec = int(round(float(min_per_km) * 60))
    minutes, seconds = divmod(max(0, total_sec), 60)
    return f'{minutes}:{seconds:02d} /км'


def _duration_seconds(duration) -> int:
    if duration is None:
        return 0
    if hasattr(duration, 'total_seconds'):
        return int(duration.total_seconds())
    try:
        return int(duration)
    except (TypeError, ValueError):
        return 0


def _averages(*, distance, duration_seconds: int, count: int, avg_speed, slug: str = '') -> dict:
    if count <= 0:
        return {
            'distance': '0',
            'distance_display': _format_distance(0),
            'duration_seconds': 0,
            'duration_display': _format_duration(0),
            'speed': None,
            'speed_display': '',
            'pace_display': '',
        }

    avg_distance = (Decimal(distance or 0) / count) if count else Decimal('0')
    avg_duration = int(duration_seconds / count) if count else 0
    speed_val = float(avg_speed) if avg_speed is not None else None
    pace_display = ''
    speed_display = ''
    if speed_val and speed_val > 0:
        if slug in PACE_SPORT_SLUGS:
            pace_display = _format_pace(60.0 / speed_val)
        else:
            speed_display = _format_speed(speed_val)

    return {
        'distance': _format_number(avg_distance),
        'distance_display': _format_distance(avg_distance),
        'duration_seconds': avg_duration,
        'duration_display': _format_duration(avg_duration),
        'speed': round(speed_val, 2) if speed_val is not None else None,
        'speed_display': speed_display,
        'pace_display': pace_display,
    }


def _bucket_payload(
    *,
    distance,
    duration,
    elevation,
    count: int,
    tss,
    avg_speed,
    slug: str = '',
    name: str = '',
    sort_order: int = 0,
) -> dict:
    duration_seconds = _duration_seconds(duration)
    distance = distance or Decimal('0')
    elevation = elevation or Decimal('0')
    tss_val = Decimal(tss or 0)
    payload = {
        'distance': _format_number(distance),
        'distance_display': _format_distance(distance),
        'duration_seconds': duration_seconds,
        'duration_display': _format_duration(duration_seconds),
        'elevation': _format_number(elevation, '0.1'),
        'elevation_display': _format_elevation(elevation),
        'count': count,
        'count_display': str(count),
        'tss': _format_number(tss_val, '0.1'),
        'tss_display': _format_number(tss_val, '0.1'),
        'averages': _averages(
            distance=distance,
            duration_seconds=duration_seconds,
            count=count,
            avg_speed=avg_speed,
            slug=slug,
        ),
    }
    if slug or name:
        payload.update({
            'slug': slug or 'unknown',
            'name': name or 'Без типа',
            'sort_order': sort_order,
        })
    return payload


def aggregate_user_year(qs, year: int) -> dict:
    start, end = year_bounds(year)
    year_qs = qs.filter(started_at__gte=start, started_at__lt=end)

    totals_row = year_qs.aggregate(
        total_distance=Coalesce(Sum('distance'), Value(Decimal('0'))),
        total_duration=Sum('duration'),
        total_elevation=Coalesce(Sum('elevation_gain'), Value(Decimal('0'))),
        total_tss=Coalesce(Sum('tss'), Value(Decimal('0'))),
        count=Count('id'),
        avg_speed=Avg(Coalesce('avg_moving_speed', 'avg_speed')),
    )

    totals = _bucket_payload(
        distance=totals_row['total_distance'],
        duration=totals_row['total_duration'],
        elevation=totals_row['total_elevation'],
        count=totals_row['count'] or 0,
        tss=totals_row['total_tss'],
        avg_speed=totals_row['avg_speed'],
    )

    by_type_rows = (
        year_qs.values(
            'activity_type_id',
            'activity_type__slug',
            'activity_type__name',
            'activity_type__sort_order',
        )
        .annotate(
            total_distance=Coalesce(Sum('distance'), Value(Decimal('0'))),
            total_duration=Sum('duration'),
            total_elevation=Coalesce(Sum('elevation_gain'), Value(Decimal('0'))),
            total_tss=Coalesce(Sum('tss'), Value(Decimal('0'))),
            count=Count('id'),
            avg_speed=Avg(Coalesce('avg_moving_speed', 'avg_speed')),
        )
        .order_by('activity_type__sort_order', 'activity_type__name')
    )

    by_type = []
    for row in by_type_rows:
        by_type.append(
            _bucket_payload(
                distance=row['total_distance'],
                duration=row['total_duration'],
                elevation=row['total_elevation'],
                count=row['count'] or 0,
                tss=row['total_tss'],
                avg_speed=row['avg_speed'],
                slug=row['activity_type__slug'] or 'unknown',
                name=row['activity_type__name'] or 'Без типа',
                sort_order=row['activity_type__sort_order'] or 1000,
            )
        )

    return {
        'year': year,
        'totals': totals,
        'by_type': by_type,
    }


def build_user_stats(qs, year: Optional[int] = None, today: Optional[Union[date_cls, datetime]] = None) -> dict:
    years = available_years(qs, today=today)
    if today is None:
        current = timezone.localdate().year
    elif isinstance(today, datetime):
        current = timezone.localtime(today).year
    else:
        current = today.year

    if year is not None:
        selected = int(year)
    else:
        selected = years[0] if years else current
    if selected not in years:
        years = sorted(set(years) | {selected}, reverse=True)

    aggregated = aggregate_user_year(qs, selected)
    return {
        'year': selected,
        'years': years,
        'totals': aggregated['totals'],
        'by_type': aggregated['by_type'],
    }


def metric_series_for_year(profile, year: int) -> dict:
    """Return ftp/weight/vo2max series for a calendar year (plus prior point)."""
    from profiles.metrics import metric_series
    from profiles.models import ProfileMetricSample

    start = date_cls(year, 1, 1)
    end = date_cls(year, 12, 31)
    result = {}
    for metric in (
        ProfileMetricSample.Metric.FTP,
        ProfileMetricSample.Metric.WEIGHT,
        ProfileMetricSample.Metric.VO2MAX,
    ):
        series = metric_series(profile, metric, start=start, end=end)
        # Carry forward: include last point before year for chart continuity.
        prior = (
            metric_series(profile, metric, end=start - timedelta(days=1))
        )
        if prior and (not series or series[0]['date'] > start.isoformat()):
            last = prior[-1]
            # Anchor at year start with last known value
            series = [{'date': start.isoformat(), 'value': last['value']}, *series]
        result[metric] = series
    return result
