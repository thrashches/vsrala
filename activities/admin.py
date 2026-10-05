from django.contrib import admin
from .models import Activity, ActivityComment, ActivityReaction, ActivityType
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
    pass


@admin.register(Activity)
class ActivityAdmin(admin.ModelAdmin):
    inlines = [
        ActivityMediaInline,
        ActivityReactionInline,
        ActivityCommentInline,
    ]


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
