import json

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
        ordering = ['-started_at']
        constraints = [
            models.UniqueConstraint(
                fields=['profile', 'external_source', 'external_id'],
                condition=~models.Q(external_id=''),
                name='unique_activity_external_id',
            ),
        ]

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
    avg_moving_speed = models.DecimalField(
        blank=True, null=True, max_digits=10, decimal_places=2,
        verbose_name='средняя скорость в движении',
    )
    max_speed = models.DecimalField(default=0.00, blank=True, null=True, decimal_places=2, max_digits=10,
                                    verbose_name='максимальная скорость')
    avg_hr = models.PositiveIntegerField(blank=True, null=True, verbose_name='средний пульс')
    max_hr = models.PositiveIntegerField(blank=True, null=True, verbose_name='максимальный пульс')
    avg_power = models.PositiveIntegerField(blank=True, null=True, verbose_name='средняя мощность')
    max_power = models.PositiveIntegerField(blank=True, null=True, verbose_name='максимальная мощность')
    normalized_power = models.PositiveIntegerField(blank=True, null=True, verbose_name='нормализованная мощность')
    tss = models.DecimalField(blank=True, null=True, max_digits=8, decimal_places=1, verbose_name='TSS')
    avg_cadence = models.PositiveIntegerField(blank=True, null=True, verbose_name='средняя частота вращения')
    max_cadence = models.PositiveIntegerField(blank=True, null=True, verbose_name='максимальная частота вращения')
    elevation_gain = models.DecimalField(blank=True, null=True, max_digits=10, decimal_places=1,
                                         verbose_name='набор высоты')
    elevation_loss = models.DecimalField(blank=True, null=True, max_digits=10, decimal_places=1,
                                         verbose_name='спуск')
    elevation_min = models.DecimalField(blank=True, null=True, max_digits=10, decimal_places=1,
                                        verbose_name='минимальная высота')
    elevation_max = models.DecimalField(blank=True, null=True, max_digits=10, decimal_places=1,
                                        verbose_name='максимальная высота')
    track_points = models.JSONField(blank=True, null=True, default=list, verbose_name='точки трека')
    streams = models.JSONField(blank=True, null=True, default=dict, verbose_name='потоки данных')
    is_indoor = models.BooleanField(default=False, verbose_name='indoor')
    zone_timeline = models.ImageField(
        blank=True, null=True, upload_to='activity_timelines',
        verbose_name='таймлайн зон',
    )
    zone_stream = models.CharField(
        max_length=16, blank=True, default='',
        verbose_name='поток для таймлайна зон',
    )
    map_preview = models.ImageField(
        blank=True, null=True, upload_to='activity_maps',
        verbose_name='превью карты',
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='дата загрузки')
    started_at = models.DateTimeField(verbose_name='время начала тренировки')
    track_file = models.FileField(blank=True, null=True, upload_to='activities', verbose_name='файл тренировки')
    external_source = models.CharField(max_length=32, blank=True, default='', verbose_name='внешний источник')
    external_id = models.CharField(max_length=64, blank=True, default='', verbose_name='внешний ID')

    def __str__(self):
        return f'{self.profile.email}: {self.title} {self.created_at}'

    @staticmethod
    def _format_hms(duration) -> str:
        total = int(duration.total_seconds()) if duration else 0
        if total < 0:
            total = 0
        hours, rem = divmod(total, 3600)
        minutes, seconds = divmod(rem, 60)
        return f'{hours:02d}:{minutes:02d}:{seconds:02d}'

    def apply_parsed_track(self, parsed):
        """Apply ParsedTrack metrics onto this activity instance (does not save)."""
        from activities.parsers.metrics import compute_tss

        self.started_at = parsed.started_at
        self.duration = parsed.duration
        self.duration_active = parsed.duration_active
        self.distance = parsed.distance_km
        self.avg_speed = parsed.avg_speed
        self.avg_moving_speed = parsed.avg_moving_speed
        self.max_speed = parsed.max_speed
        self.avg_hr = parsed.avg_hr
        self.max_hr = parsed.max_hr
        self.avg_power = parsed.avg_power
        self.max_power = parsed.max_power
        self.normalized_power = parsed.normalized_power
        self.avg_cadence = parsed.avg_cadence
        self.max_cadence = parsed.max_cadence
        self.elevation_gain = parsed.elevation_gain
        self.elevation_loss = parsed.elevation_loss
        self.elevation_min = parsed.elevation_min
        self.elevation_max = parsed.elevation_max
        self.track_points = parsed.points
        self.streams = parsed.streams
        self.is_indoor = not bool(parsed.points)

        if parsed.tss is not None:
            self.tss = parsed.tss
        else:
            ftp = None
            try:
                ftp = self.profile.ftp
            except Exception:
                pass
            moving = parsed.duration_active.total_seconds() if parsed.duration_active else 0
            self.tss = compute_tss(parsed.normalized_power, moving, ftp)

    @property
    def track_points_json(self):
        return json.dumps(self.track_points or [])

    @property
    def streams_json(self):
        return json.dumps(self.streams or {})

    @property
    def duration_display(self):
        return self._format_hms(self.duration)

    @property
    def duration_active_display(self):
        return self._format_hms(self.duration_active)

    def save(self, force_insert=False, force_update=False, using=None, update_fields=None):
        if (self.title == '' or self.title is None) and self.started_at:
            t = self.started_at.time()
            if time(hour=5) <= t <= time(hour=12):
                self.title = 'Утренняя тренировка'
            elif time(hour=12, minute=1) <= t <= time(hour=18):
                self.title = 'Дневная тренировка'
            elif time(hour=18, minute=1) <= t <= time(hour=23):
                self.title = 'Вечерняя тренировка'
            else:
                self.title = 'Ночная тренировка'
        super().save(force_insert=force_insert, force_update=force_update, using=using,
                     update_fields=update_fields)


class ActivityReaction(models.Model):
    EMOJI_LIKE = '👍'
    EMOJI_FIRE = '🔥'
    EMOJI_CLAP = '👏'
    EMOJI_EGGPLANT = '🍆'
    EMOJI_BANANA = '🍌'
    EMOJI_HEART = '❤️'

    EMOJI_CHOICES = [
        (EMOJI_LIKE, 'Лайк'),
        (EMOJI_FIRE, 'Огонёк'),
        (EMOJI_CLAP, 'Аплодисменты'),
        (EMOJI_EGGPLANT, 'Баклажан'),
        (EMOJI_BANANA, 'Банан'),
        (EMOJI_HEART, 'Сердечко'),
    ]
    ALLOWED_EMOJIS = {choice[0] for choice in EMOJI_CHOICES}

    class Meta:
        verbose_name = 'реакция'
        verbose_name_plural = 'реакции'
        constraints = [
            models.UniqueConstraint(
                fields=['activity', 'profile'],
                name='unique_activity_reaction_per_profile',
            ),
        ]

    activity = models.ForeignKey(
        Activity,
        on_delete=models.CASCADE,
        related_name='reactions',
        verbose_name='тренировка',
    )
    profile = models.ForeignKey(
        Profile,
        on_delete=models.CASCADE,
        related_name='activity_reactions',
        verbose_name='пользователь',
    )
    emoji = models.CharField(max_length=8, choices=EMOJI_CHOICES, verbose_name='эмодзи')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='дата')

    def __str__(self):
        return f'{self.profile_id}:{self.activity_id}:{self.emoji}'


class ActivityComment(models.Model):
    class Meta:
        verbose_name = 'комментарий'
        verbose_name_plural = 'комментарии'
        ordering = ['created_at']

    activity = models.ForeignKey(
        Activity,
        on_delete=models.CASCADE,
        related_name='comments',
        verbose_name='тренировка',
    )
    profile = models.ForeignKey(
        Profile,
        on_delete=models.CASCADE,
        related_name='activity_comments',
        verbose_name='пользователь',
    )
    text = models.TextField(max_length=2000, verbose_name='текст')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='дата создания')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='дата изменения')

    def __str__(self):
        return f'{self.profile_id}:{self.activity_id}:{self.pk}'
