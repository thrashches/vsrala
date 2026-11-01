from datetime import date as date_cls, datetime
from decimal import Decimal
from typing import Optional, Union
from zoneinfo import ZoneInfo

from django.conf import settings
from django.db.models import Count, Sum, Value
from django.db.models.functions import Coalesce, ExtractYear
from django.utils import timezone

from activities.leaderboard import _format_distance, _format_duration


def _tz():
    return ZoneInfo(settings.TIME_ZONE)


def _today(today: Optional[Union[date_cls, datetime]] = None) -> date_cls:
    tz = _tz()
    if today is None:
        return timezone.now().astimezone(tz).date()
    if isinstance(today, datetime):
        return today.astimezone(tz).date()
    return today


def year_bounds(year: int):
    """Return [start, end) datetimes for a calendar year in project TZ."""
    tz = _tz()
    start = timezone.make_aware(datetime(year, 1, 1), tz)
    end = timezone.make_aware(datetime(year + 1, 1, 1), tz)
    return start, end


def _format_elevation(meters) -> str:
    value = Decimal(meters or 0).quantize(Decimal('0.1'))
    text = f'{value:f}'.rstrip('0').rstrip('.')
    return f'{text} м'


def _format_distance_value(km) -> str:
    value = Decimal(km or 0).quantize(Decimal('0.01'))
    return f'{value:f}'.rstrip('0').rstrip('.')


def _format_elevation_value(meters) -> str:
    value = Decimal(meters or 0).quantize(Decimal('0.1'))
    return f'{value:f}'.rstrip('0').rstrip('.')


def available_years(qs, today: Optional[Union[date_cls, datetime]] = None) -> list[int]:
    """Distinct activity years (project TZ), newest first; always includes current year."""
    current = _today(today).year
    years = set(
        qs.annotate(y=ExtractYear('started_at', tzinfo=_tz()))
        .values_list('y', flat=True)
        .distinct()
    )
    years.discard(None)
    years.add(current)
    return sorted((int(y) for y in years), reverse=True)


def aggregate_year(qs, year: int) -> dict:
    start, end = year_bounds(year)
    row = qs.filter(started_at__gte=start, started_at__lt=end).aggregate(
        total_distance=Coalesce(Sum('distance'), Value(Decimal('0'))),
        total_duration=Sum('duration'),
        total_elevation=Coalesce(Sum('elevation_gain'), Value(Decimal('0'))),
        count=Count('id'),
    )
    distance = row['total_distance'] or Decimal('0')
    duration = row['total_duration']
    elevation = row['total_elevation'] or Decimal('0')
    count = row['count'] or 0
    duration_seconds = int(duration.total_seconds()) if duration else 0

    return {
        'distance': _format_distance_value(distance),
        'distance_display': _format_distance(distance),
        'duration_display': _format_duration(duration_seconds),
        'elevation': _format_elevation_value(elevation),
        'elevation_display': _format_elevation(elevation),
        'count': count,
        'count_display': str(count),
    }


def build_year_stats(qs, today: Optional[Union[date_cls, datetime]] = None) -> dict:
    """Aggregate yearly stats for an already-visibility-filtered activity queryset."""
    selected_year = _today(today).year
    years = available_years(qs, today=today)
    by_year = {year: aggregate_year(qs, year) for year in years}
    return {
        'years': years,
        'selected_year': selected_year,
        'by_year': by_year,
    }
