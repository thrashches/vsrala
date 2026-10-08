from __future__ import annotations

import json
import math

from django.db import models
from django.db.models import Q
from django.contrib.auth import get_user_model

Profile = get_user_model()


class RouteQuerySet(models.QuerySet):
    def visible_to(self, user):
        if not user or not user.is_authenticated:
            return self.none()
        following_ids = list(user.follows.values_list('pk', flat=True))
        return self.filter(
            Q(profile=user)
            | Q(visibility=Route.Visibility.PUBLIC)
            | Q(visibility=Route.Visibility.FOLLOWERS, profile_id__in=following_ids)
        )


class Route(models.Model):
    class Visibility(models.TextChoices):
        PRIVATE = 'private', 'Только я'
        FOLLOWERS = 'followers', 'Подписчики'
        PUBLIC = 'public', 'Все'

    class SurfaceStatus(models.TextChoices):
        PENDING = 'pending', 'Ожидает'
        READY = 'ready', 'Готово'
        FAILED = 'failed', 'Ошибка'
        SKIPPED = 'skipped', 'Пропущено'

    class Meta:
        verbose_name = 'маршрут'
        verbose_name_plural = 'маршруты'
        ordering = ['-created_at']

    objects = RouteQuerySet.as_manager()

    profile = models.ForeignKey(
        Profile, on_delete=models.CASCADE, related_name='routes',
        verbose_name='владелец',
    )
    title = models.CharField(max_length=255, blank=True, default='', verbose_name='название')
    description = models.TextField(blank=True, default='', max_length=3000, verbose_name='описание')
    visibility = models.CharField(
        max_length=16,
        choices=Visibility.choices,
        default=Visibility.PRIVATE,
        verbose_name='видимость',
    )
    track_points = models.JSONField(blank=True, default=list, verbose_name='точки маршрута')
    distance = models.DecimalField(
        default=0, max_digits=10, decimal_places=2, verbose_name='дистанция (км)',
    )
    elevation_gain = models.DecimalField(
        blank=True, null=True, max_digits=10, decimal_places=1, verbose_name='набор высоты',
    )
    elevation_loss = models.DecimalField(
        blank=True, null=True, max_digits=10, decimal_places=1, verbose_name='спуск',
    )
    map_preview = models.ImageField(
        blank=True, null=True, upload_to='route_maps', verbose_name='превью карты',
    )
    source_gpx = models.FileField(
        blank=True, null=True, upload_to='routes', verbose_name='исходный GPX',
    )
    source_activity = models.ForeignKey(
        'activities.Activity',
        blank=True,
        null=True,
        on_delete=models.SET_NULL,
        related_name='derived_routes',
        verbose_name='исходная тренировка',
    )
    surface_segments = models.JSONField(
        blank=True, default=list, verbose_name='сегменты покрытия',
    )
    surface_status = models.CharField(
        max_length=16,
        choices=SurfaceStatus.choices,
        default=SurfaceStatus.PENDING,
        verbose_name='статус покрытия',
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='создан')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='обновлён')

    def __str__(self):
        return f'{self.profile.email}: {self.title or f"Route #{self.pk}"}'

    def is_visible_to(self, user) -> bool:
        if not user or not user.is_authenticated:
            return False
        if self.profile_id == user.pk:
            return True
        if self.visibility == self.Visibility.PUBLIC:
            return True
        if self.visibility == self.Visibility.FOLLOWERS:
            return user.follows.filter(pk=self.profile_id).exists()
        return False

    @property
    def track_points_json(self) -> str:
        return json.dumps(self.track_points or [])

    @property
    def surface_segments_json(self) -> str:
        return json.dumps(self.surface_segments or [])

    @property
    def visibility_label(self) -> str:
        return self.get_visibility_display()

    def surface_summary(self) -> list[dict]:
        """Aggregate distance_m by surface for UI bars."""
        totals: dict[str, float] = {}
        for seg in self.surface_segments or []:
            key = seg.get('surface') or 'unknown'
            totals[key] = totals.get(key, 0.0) + float(seg.get('distance_m') or 0)
        total = sum(totals.values()) or 1.0
        order = sorted(totals.items(), key=lambda x: -x[1])
        return [
            {
                'surface': name,
                'distance_m': round(dist, 1),
                'pct': round(100.0 * dist / total, 1),
            }
            for name, dist in order
        ]


def haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def distance_km_from_points(points: list) -> float:
    if not points or len(points) < 2:
        return 0.0
    total = 0.0
    for i in range(1, len(points)):
        try:
            lat1, lon1 = float(points[i - 1][0]), float(points[i - 1][1])
            lat2, lon2 = float(points[i][0]), float(points[i][1])
        except (TypeError, ValueError, IndexError):
            continue
        total += haversine_m(lat1, lon1, lat2, lon2)
    return round(total / 1000.0, 2)


def strip_time_from_points(points: list) -> list:
    out = []
    for p in points or []:
        if not p or len(p) < 2:
            continue
        try:
            out.append([float(p[0]), float(p[1])])
        except (TypeError, ValueError):
            continue
    return out
