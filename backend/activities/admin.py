from django.contrib import admin, messages

from .models import Activity, ActivityComment, ActivityReaction, ActivityType, WeatherForecast
from .tasks import generate_map_previews_for_activities, update_activity_types_from_fit_task
from user_medias.models import ActivityMedia


class ActivityMediaInline(admin.StackedInline):
    model = ActivityMedia


class ActivityReactionInline(admin.TabularInline):
    model = ActivityReaction
    extra = 0
    readonly_fields = ('created_at',)


class ActivityCommentInline(admin.TabularInline):
    model = ActivityComment
    extra = 0
    readonly_fields = ('created_at', 'updated_at')


@admin.register(ActivityType)
class ActivityTypeAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug', 'sort_order')
    search_fields = ('name', 'slug')
    ordering = ('sort_order', 'name')


@admin.register(Activity)
class ActivityAdmin(admin.ModelAdmin):
    list_display = ('id', 'title', 'profile', 'activity_type', 'started_at', 'external_source')
    list_filter = ('activity_type', 'external_source', 'is_indoor')
    search_fields = ('title', 'profile__email', 'external_id')
    raw_id_fields = ('profile', 'activity_type')
    inlines = [
        ActivityMediaInline,
        ActivityReactionInline,
        ActivityCommentInline,
    ]
    actions = [
        'enqueue_map_preview_generation',
        'update_types_from_fit',
    ]

    @admin.action(description='Сгенерировать превью карты (фоном)')
    def enqueue_map_preview_generation(self, request, queryset):
        activity_ids = list(queryset.values_list('pk', flat=True))
        if not activity_ids:
            self.message_user(request, 'Не выбрано ни одной активности.', messages.WARNING)
            return
        generate_map_previews_for_activities.delay(activity_ids)
        self.message_user(
            request,
            f'Запущена фоновая генерация превью для {len(activity_ids)} активност(ей).',
            messages.SUCCESS,
        )

    @admin.action(description='Обновить тип из FIT-файла (фоном)')
    def update_types_from_fit(self, request, queryset):
        activity_ids = list(queryset.values_list('pk', flat=True))
        if not activity_ids:
            self.message_user(request, 'Не выбрано ни одной активности.', messages.WARNING)
            return
        update_activity_types_from_fit_task.delay(activity_ids)
        self.message_user(
            request,
            f'Запущено фоновое обновление типов из FIT для {len(activity_ids)} активност(ей).',
            messages.SUCCESS,
        )


@admin.register(WeatherForecast)
class WeatherForecastAdmin(admin.ModelAdmin):
    list_display = ('id', 'lat', 'lon', 'period_start', 'period_end', 'status', 'fetched_at')
    list_filter = ('status', 'source')
    search_fields = ('error',)


@admin.register(ActivityReaction)
class ActivityReactionAdmin(admin.ModelAdmin):
    list_display = ('activity', 'profile', 'emoji', 'created_at')
    list_filter = ('emoji',)
    search_fields = ('profile__email', 'activity__title')


@admin.register(ActivityComment)
class ActivityCommentAdmin(admin.ModelAdmin):
    list_display = ('activity', 'profile', 'created_at', 'updated_at')
    search_fields = ('profile__email', 'activity__title', 'text')
    readonly_fields = ('created_at', 'updated_at')
