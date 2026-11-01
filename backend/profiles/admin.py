from django.contrib import admin, messages
from django.contrib.auth.admin import UserAdmin
from django.utils.translation import gettext_lazy as _

from .models import FollowRequest, Profile
from .photo_preview import apply_photo_preview, clear_photo_preview
from .tasks import generate_photo_previews_for_profiles


class FollowsInline(admin.TabularInline):
    model = Profile.follows.through
    fk_name = 'user'


@admin.register(Profile)
class ProfileAdmin(UserAdmin):
    ordering = ['-id']
    fieldsets = (
        (None, {'fields': ('email', 'password')}),
        (_('Personal info'), {
            'fields': (
                'first_name', 'last_name', 'photo', 'photo_preview',
                'telegram', 'instagram', 'vk', 'is_public',
            ),
        }),
        (_('Permissions'), {'fields': ('is_active', 'is_staff', 'is_superuser',
                                       'groups', 'user_permissions')}),
        (_('Important dates'), {'fields': ('last_login', 'date_joined')}),
    )
    readonly_fields = ('photo_preview',)
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('email', 'password1', 'password2'),
        }),
    )
    list_display = ('email', 'first_name', 'last_name', 'is_public', 'is_staff')
    search_fields = ('email', 'first_name', 'last_name')
    list_filter = ('is_public', 'is_staff', 'is_active')
    inlines = [
        FollowsInline,
    ]
    actions = ['enqueue_photo_preview_generation']

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        if 'photo' in form.changed_data:
            if obj.photo:
                apply_photo_preview(obj)
            else:
                clear_photo_preview(obj)

    @admin.action(description='Сгенерировать превью аватара (фоном)')
    def enqueue_photo_preview_generation(self, request, queryset):
        profile_ids = list(queryset.values_list('pk', flat=True))
        if not profile_ids:
            self.message_user(request, 'Не выбран ни один профиль.', messages.WARNING)
            return
        generate_photo_previews_for_profiles.delay(profile_ids)
        self.message_user(
            request,
            f'Запущена фоновая генерация превью аватара для {len(profile_ids)} профил(ей).',
            messages.SUCCESS,
        )


@admin.register(FollowRequest)
class FollowRequestAdmin(admin.ModelAdmin):
    list_display = ('from_user', 'to_user', 'created_at')
    search_fields = ('from_user__email', 'to_user__email')
    raw_id_fields = ('from_user', 'to_user')
