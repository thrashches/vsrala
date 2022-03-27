import folium
from parsers.gpx import GPXActivity
import io

from PIL import Image
from django.db import models

from django.contrib.auth import get_user_model
from datetime import timedelta, time

Profile = get_user_model()


class ActivityType(models.Model):
    class Meta:
        verbose_name = 'тип тренировки'
        verbose_name_plural = 'типы тренировок'

    name = models.CharField(max_length=255, unique=True, verbose_name='название')

    def __str__(self):
        return self.name


class Activity(models.Model):
    class Meta:
        verbose_name = 'тренировка'
        verbose_name_plural = 'тренировки'
        ordering = ['-created_at', ]

    title = models.CharField(max_length=255, default='',
                             blank=True, null=True,
                             verbose_name='название тренировки')
    description = models.TextField(blank=True, null=True, max_length=3000, verbose_name='описание тренировки')
    profile = models.ForeignKey(Profile, on_delete=models.CASCADE, verbose_name='спортсмен')
    activity_type = models.ForeignKey(ActivityType,
                                      blank=True, null=True,
                                      on_delete=models.SET_NULL, verbose_name='тип тренировки')
    duration = models.DurationField(default=timedelta(minutes=0, seconds=0), verbose_name='продолжительность')
    duration_active = models.DurationField(default=timedelta(minutes=0, seconds=0),
                                           blank=True, null=True,
                                           verbose_name='время в движении')
    distance = models.DecimalField(default=0.00, max_digits=10, decimal_places=2, verbose_name='дистанция')
    avg_speed = models.DecimalField(default=0.00,
                                    blank=True, null=True, max_digits=10, decimal_places=2,
                                    verbose_name='средняя скорость')
    max_speed = models.DecimalField(default=0.00, blank=True, null=True, decimal_places=2, max_digits=10,
                                    verbose_name='максимальная скорость')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='дата загрузки')
    started_at = models.DateTimeField(verbose_name='время начала тренировки')
    track_file = models.FileField(blank=True, null=True, upload_to='activities', verbose_name='файл тренировки')

    def __str__(self):
        return f'{self.profile.email}: {self.title} {self.created_at}'

    def save(
            self, force_insert=False, force_update=False, using=None, update_fields=None
    ):
        create = not self.pk
        if self.title == '' or self.title is None:
            if time(hour=5) <= self.started_at.time() <= time(hour=12):
                self.title = 'Утренняя тренировка'
            elif time(hour=12, minute=1) <= self.started_at.time() <= time(hour=18):
                self.title = 'Вечерняя тренировка'
            elif time(hour=18, minute=1) <= self.started_at.time() <= time(hour=23):
                self.title = 'Вечерняя тренировка'
            elif time(hour=23, minute=1) <= self.started_at.time() or \
                    self.started_at.time() <= time(hour=5):
                self.title = 'Ночная тренировка'
        super(Activity, self).save(force_insert=force_insert, force_update=force_update, using=using,
                                   update_fields=update_fields)

        if create and self.track_file:
            print(self.track_file.path)
            gpx = GPXActivity.fromfile(self.track_file.path)

            # TODO: Этот кусок рисует точки на карте, а потом рендерит в картинку. Его потом сделаем как микросервис
            # points = []
            # for track in gpx.tracks:
            #     for segment in track.segments:
            #         for point in segment.points:
            #             points.append(tuple([point.latitude, point.longitude]))
            # latitude = sum(p[0] for p in points) / len(points)
            # longitude = sum(p[1] for p in points) / len(points)
            # folium_map = folium.Map(location=[latitude, longitude], zoom_start=10)
            # folium.PolyLine(points, color="red", weight=2.5, opacity=1).add_to(folium_map)
            # img = folium_map._to_png(5)
            # output = Image.open(io.BytesIO(img))
            self.max_speed = gpx.speed_max
            self.avg_speed = gpx.speed_avg
            self.distance = gpx.distance / 1000
            self.duration = gpx.duration
            self.duration_active = gpx.duration_active
            # TODO: hr, power,cadence...
            super(Activity, self).save(force_insert=force_insert, force_update=force_update, using=using,
                                       update_fields=update_fields)
            # output.save('media/pictures/test.png')
