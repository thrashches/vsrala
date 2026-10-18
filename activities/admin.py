from django.contrib import admin, messages

from .models import Activity, ActivityComment, ActivityReaction, ActivityType
from .tasks import generate_map_previews_for_activities
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
    actions = ['enqueue_map_preview_generation']

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
