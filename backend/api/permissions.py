from rest_framework.permissions import BasePermission


def user_can_view_activity(user, activity) -> bool:
    if activity.profile_id == user.pk:
        return True
    if activity.profile.is_public:
        return True
    return user.follows.filter(pk=activity.profile_id).exists()


def visible_activities_for(viewer, owner):
    from activities.models import Activity

    qs = (
        Activity.objects.filter(profile=owner)
        .select_related('profile', 'activity_type')
        .prefetch_related('medias')
    )
    if owner.pk == viewer.pk or owner.is_public:
        return qs
    if viewer.follows.filter(pk=owner.pk).exists():
        return qs
    return qs.none()


class IsActivityOwner(BasePermission):
    def has_object_permission(self, request, view, obj):
        return obj.profile_id == request.user.pk


class CanViewActivity(BasePermission):
    def has_object_permission(self, request, view, obj):
        return user_can_view_activity(request.user, obj)


class IsRouteOwner(BasePermission):
    def has_object_permission(self, request, view, obj):
        return obj.profile_id == request.user.pk


class CanViewRoute(BasePermission):
    def has_object_permission(self, request, view, obj):
        return obj.is_visible_to(request.user)
