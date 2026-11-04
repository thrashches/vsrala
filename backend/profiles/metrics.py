from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Optional, Union

from django.utils import timezone

from .models import Profile, ProfileMetricSample


def _to_decimal(value) -> Optional[Decimal]:
    if value is None or value == '':
        return None
    try:
        dec = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return None
    if not dec.is_finite():
        return None
    return dec


def _as_date(value: Union[date, datetime, str]) -> date:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value)[:10])


def upsert_metric_sample(
    profile: Profile,
    *,
    metric: str,
    recorded_on: Union[date, datetime, str],
    value,
    source: str,
    external_key: str = '',
    update_profile_ftp: bool = True,
) -> Optional[ProfileMetricSample]:
    """Create or update a daily metric sample. Returns None if value is invalid."""
    dec = _to_decimal(value)
    if dec is None:
        return None
    if metric == ProfileMetricSample.Metric.FTP and dec <= 0:
        return None
    if metric == ProfileMetricSample.Metric.WEIGHT and dec <= 0:
        return None
    if metric == ProfileMetricSample.Metric.VO2MAX and dec <= 0:
        return None

    day = _as_date(recorded_on)
    sample, _created = ProfileMetricSample.objects.update_or_create(
        profile=profile,
        metric=metric,
        recorded_on=day,
        source=source,
        defaults={
            'value': dec,
            'external_key': (external_key or '')[:128],
        },
    )

    if (
        update_profile_ftp
        and metric == ProfileMetricSample.Metric.FTP
        and source in (
            ProfileMetricSample.Source.GARMIN,
            ProfileMetricSample.Source.INTERVALS,
            ProfileMetricSample.Source.PROFILE,
        )
    ):
        today = timezone.localdate()
        latest = (
            ProfileMetricSample.objects.filter(
                profile=profile,
                metric=ProfileMetricSample.Metric.FTP,
            )
            .order_by('-recorded_on', '-updated_at')
            .first()
        )
        if latest and latest.pk == sample.pk and day <= today:
            ftp_int = int(dec)
            if profile.ftp != ftp_int:
                profile.ftp = ftp_int
                profile.save(update_fields=['ftp'])

    return sample


def metric_series(
    profile: Profile,
    metric: str,
    *,
    start: Optional[date] = None,
    end: Optional[date] = None,
) -> list[dict]:
    """
    Collapse samples from multiple sources into one point per day.
    Preference: garmin > intervals > activity > profile.
    """
    qs = ProfileMetricSample.objects.filter(profile=profile, metric=metric)
    if start is not None:
        qs = qs.filter(recorded_on__gte=start)
    if end is not None:
        qs = qs.filter(recorded_on__lte=end)
    qs = qs.order_by('recorded_on', 'id')

    priority = {
        ProfileMetricSample.Source.GARMIN: 0,
        ProfileMetricSample.Source.INTERVALS: 1,
        ProfileMetricSample.Source.ACTIVITY: 2,
        ProfileMetricSample.Source.PROFILE: 3,
    }
    by_day: dict[date, tuple[int, Decimal]] = {}
    for sample in qs:
        prio = priority.get(sample.source, 99)
        existing = by_day.get(sample.recorded_on)
        if existing is None or prio < existing[0]:
            by_day[sample.recorded_on] = (prio, sample.value)

    return [
        {'date': day.isoformat(), 'value': float(value)}
        for day, (_prio, value) in sorted(by_day.items())
    ]
