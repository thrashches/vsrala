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

    title = models.CharField(max_length=255, default='',
                             blank=True, null=True,
                             verbose_name='название тренировки')
    description = models.TextField(blank=True, null=True, max_length=3000, verbose_name='описание тренировки')
    profile = models.ForeignKey(Profile, on_delete=models.CASCADE, verbose_name='спортсмен')
    activity_type = models.ForeignKey(ActivityType,
                                      blank=True, null=True,
                                      on_delete=models.SET_NULL, verbose_name='тип тренировки')
    duration = models.DurationField(default=timedelta(minutes=0, seconds=0), verbose_name='продолжительность')
    distance = models.DecimalField(default=0.00, max_digits=10, decimal_places=2, verbose_name='дистанция')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='дата загрузки')
    started_at = models.DateTimeField(verbose_name='время начала тренировки')
    track_file = models.FileField(blank=True, null=True, upload_to='activities', verbose_name='файл тренировки')

    def __str__(self):
        return f'{self.profile.email}: {self.title} {self.created_at}'

    def save(
            self, force_insert=False, force_update=False, using=None, update_fields=None
    ):
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
