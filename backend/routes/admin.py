from django.contrib import admin, messages

from .models import Route
from .services import enqueue_surface_enrichment


@admin.register(Route)
class RouteAdmin(admin.ModelAdmin):
    list_display = (
        'title', 'profile', 'visibility', 'distance', 'surface_status', 'created_at',
    )
    list_filter = ('visibility', 'surface_status')
    search_fields = ('title', 'profile__email', 'description')
    readonly_fields = ('created_at', 'updated_at')
    raw_id_fields = ('profile', 'source_activity')
    actions = ['enqueue_surface_reanalysis']

    @admin.action(description='Переанализировать покрытие (фоном)')
    def enqueue_surface_reanalysis(self, request, queryset):
        route_ids = list(queryset.values_list('pk', flat=True))
        if not route_ids:
            self.message_user(request, 'Не выбран ни один маршрут.', messages.WARNING)
            return
        for route_id in route_ids:
            enqueue_surface_enrichment(route_id)
        self.message_user(
            request,
            f'Запущен повторный анализ покрытия для {len(route_ids)} маршрут(ов).',
            messages.SUCCESS,
        )
