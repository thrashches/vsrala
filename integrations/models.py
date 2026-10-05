from django.conf import settings
from django.db import models


class IntervalsConnection(models.Model):
    class Meta:
        verbose_name = 'подключение Intervals.icu'
        verbose_name_plural = 'подключения Intervals.icu'

    profile = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='intervals_connection',
        verbose_name='спортсмен',
    )
    api_key = models.CharField(max_length=255, verbose_name='API-ключ')
    athlete_id = models.CharField(max_length=64, blank=True, verbose_name='ID атлета')
    is_active = models.BooleanField(default=False, verbose_name='активно')
    initial_sync_done = models.BooleanField(default=False, verbose_name='начальная синхронизация выполнена')
    last_synced_at = models.DateTimeField(blank=True, null=True, verbose_name='последняя синхронизация')
    last_error = models.TextField(blank=True, verbose_name='последняя ошибка')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='создано')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='обновлено')

    def __str__(self):
        status = 'активно' if self.is_active else 'неактивно'
        return f'{self.profile.email}: Intervals.icu ({status})'
