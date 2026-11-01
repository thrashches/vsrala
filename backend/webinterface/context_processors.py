from profiles.models import FollowRequest


def follow_requests(request):
    count = 0
    user = getattr(request, 'user', None)
    if user is not None and user.is_authenticated:
        count = FollowRequest.objects.filter(to_user=user).count()
    return {'pending_follow_requests_count': count}
