from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import FollowRequest, Profile
from django.utils.translation import gettext_lazy as _


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
                'first_name', 'last_name', 'photo',
                'telegram', 'instagram', 'vk', 'is_public',
            ),
        }),
        (_('Permissions'), {'fields': ('is_active', 'is_staff', 'is_superuser',
                                       'groups', 'user_permissions')}),
        (_('Important dates'), {'fields': ('last_login', 'date_joined')}),
    )
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


@admin.register(FollowRequest)
class FollowRequestAdmin(admin.ModelAdmin):
    list_display = ('from_user', 'to_user', 'created_at')
    search_fields = ('from_user__email', 'to_user__email')
    raw_id_fields = ('from_user', 'to_user')
