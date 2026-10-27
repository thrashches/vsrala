from __future__ import annotations

from dataclasses import dataclass

from django.core.exceptions import ValidationError

from profiles.models import Follow, FollowRequest, Profile


@dataclass
class FollowToggleResult:
    is_following: bool
    request_pending: bool
    followers_count: int


def toggle_follow(*, viewer: Profile, target: Profile) -> FollowToggleResult:
    """Toggle follow / cancel pending request / create follow or request."""
    if target.pk == viewer.pk:
        raise ValidationError('Нельзя подписаться на себя')

    follow = Follow.objects.filter(user=viewer, following=target).first()
    pending = FollowRequest.objects.filter(from_user=viewer, to_user=target).first()
    is_following = False
    request_pending = False

    if follow:
        follow.delete()
        if pending:
            pending.delete()
    elif pending:
        pending.delete()
    else:
        they_follow_me = Follow.objects.filter(
            user=target, following=viewer,
        ).exists()
        if target.is_public or they_follow_me:
            Follow.objects.create(user=viewer, following=target)
            is_following = True
        else:
            FollowRequest.objects.create(from_user=viewer, to_user=target)
            request_pending = True

    return FollowToggleResult(
        is_following=is_following,
        request_pending=request_pending,
        followers_count=target.followers.count(),
    )


def accept_follow_request(*, follow_request: FollowRequest) -> None:
    Follow.objects.get_or_create(
        user=follow_request.from_user,
        following=follow_request.to_user,
    )
    follow_request.delete()


def reject_follow_request(*, follow_request: FollowRequest) -> None:
    follow_request.delete()
