from django.contrib import admin, messages

from .models import GarminConnection, IntervalsConnection
from .tasks import sync_connection


@admin.register(IntervalsConnection)
class IntervalsConnectionAdmin(admin.ModelAdmin):
    list_display = ('profile', 'athlete_id', 'is_active', 'initial_sync_done', 'last_synced_at')
    list_filter = ('is_active', 'initial_sync_done')
    search_fields = ('profile__email', 'athlete_id')
    readonly_fields = ('created_at', 'updated_at', 'last_synced_at')
    actions = ['enqueue_initial_sync']

    @admin.action(description='Синхронизировать с начала года (фоном)')
    def enqueue_initial_sync(self, request, queryset):
        enqueued = 0
        skipped = 0
        for connection in queryset:
            if not connection.is_active or not connection.api_key:
                skipped += 1
                continue
            sync_connection.delay(connection.pk, initial=True)
            enqueued += 1
        if enqueued:
            self.message_user(
                request,
                f'Запущена фоновая синхронизация с начала года для {enqueued} подключени(й).',
                messages.SUCCESS,
            )
        if skipped:
            self.message_user(
                request,
                f'Пропущено {skipped} неактивных или без API-ключа.',
                messages.WARNING,
            )
        if not enqueued and not skipped:
            self.message_user(request, 'Не выбрано ни одного подключения.', messages.WARNING)


@admin.register(GarminConnection)
class GarminConnectionAdmin(admin.ModelAdmin):
    list_display = (
        'profile', 'garmin_user_id', 'is_active', 'initial_sync_done', 'last_synced_at',
    )
    list_filter = ('is_active', 'initial_sync_done')
    search_fields = ('profile__email', 'garmin_user_id')
    readonly_fields = ('created_at', 'updated_at', 'last_synced_at', 'token_expires_at')
