from django.contrib import admin

from .models import Route


@admin.register(Route)
class RouteAdmin(admin.ModelAdmin):
    list_display = (
        'title', 'profile', 'visibility', 'distance', 'surface_status', 'created_at',
    )
    list_filter = ('visibility', 'surface_status')
    search_fields = ('title', 'profile__email', 'description')
    readonly_fields = ('created_at', 'updated_at')
    raw_id_fields = ('profile', 'source_activity')
