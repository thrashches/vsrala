from django.contrib import admin
from .models import ActivityType, Activity
from user_medias.models import ActivityMedia


class ActivityMediaInline(admin.StackedInline):
    model = ActivityMedia


@admin.register(ActivityType)
class ActivityTypeAdmin(admin.ModelAdmin):
    pass


@admin.register(Activity)
class ActivityAdmin(admin.ModelAdmin):
    inlines = [
        ActivityMediaInline,
    ]
