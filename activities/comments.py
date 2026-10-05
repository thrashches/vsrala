from activities.models import ActivityComment

COMMENT_TEXT_MAX_LENGTH = 2000


def comment_count_label(count):
    """Russian plural for comment counts."""
    n = abs(int(count))
    mod10 = n % 10
    mod100 = n % 100
    if mod10 == 1 and mod100 != 11:
        word = 'комментарий'
    elif 2 <= mod10 <= 4 and not (12 <= mod100 <= 14):
        word = 'комментария'
    else:
        word = 'комментариев'
    return f'{n} {word}'


def can_edit_comment(comment, user):
    return user.is_authenticated and comment.profile_id == user.pk


def can_delete_comment(comment, user):
    if not user.is_authenticated:
        return False
    if comment.profile_id == user.pk:
        return True
    return comment.activity.profile_id == user.pk


def serialize_comment(comment, user):
    profile = comment.profile
    photo_url = ''
    if getattr(profile, 'photo', None):
        try:
            photo_url = profile.photo.url
        except ValueError:
            photo_url = ''
    return {
        'id': comment.pk,
        'text': comment.text,
        'created_at': comment.created_at.isoformat(),
        'updated_at': comment.updated_at.isoformat(),
        'profile': {
            'id': profile.pk,
            'display_name': profile.display_name,
            'photo_url': photo_url,
            'initial': (profile.email[:1] or '?').upper(),
        },
        'can_edit': can_edit_comment(comment, user),
        'can_delete': can_delete_comment(comment, user),
    }


def create_comment(activity, profile, text):
    cleaned = (text or '').strip()
    if not cleaned:
        raise ValueError('empty')
    if len(cleaned) > COMMENT_TEXT_MAX_LENGTH:
        raise ValueError('too_long')
    return ActivityComment.objects.create(
        activity=activity,
        profile=profile,
        text=cleaned,
    )


def update_comment(comment, text):
    cleaned = (text or '').strip()
    if not cleaned:
        raise ValueError('empty')
    if len(cleaned) > COMMENT_TEXT_MAX_LENGTH:
        raise ValueError('too_long')
    comment.text = cleaned
    comment.save(update_fields=['text', 'updated_at'])
    return comment
