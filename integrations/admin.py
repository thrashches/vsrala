from django.contrib import admin

from .models import IntervalsConnection


@admin.register(IntervalsConnection)
class IntervalsConnectionAdmin(admin.ModelAdmin):
    list_display = ('profile', 'athlete_id', 'is_active', 'initial_sync_done', 'last_synced_at')
    list_filter = ('is_active', 'initial_sync_done')
    search_fields = ('profile__email', 'athlete_id')
    readonly_fields = ('created_at', 'updated_at', 'last_synced_at')
