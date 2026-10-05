from collections import defaultdict

from django.db.models import Count

from activities.models import ActivityReaction

EMOJI_ORDER = {emoji: idx for idx, (emoji, _) in enumerate(ActivityReaction.EMOJI_CHOICES)}


def _sort_counts(counts):
    return sorted(counts, key=lambda item: EMOJI_ORDER.get(item['emoji'], 99))


def reaction_summary_for_activities(activity_ids, profile):
    """Return {activity_id: {'counts': [{emoji, count}], 'mine': emoji|None}}."""
    result = {pk: {'counts': [], 'mine': None} for pk in activity_ids}
    if not activity_ids:
        return result

    counts_qs = (
        ActivityReaction.objects.filter(activity_id__in=activity_ids)
        .values('activity_id', 'emoji')
        .annotate(count=Count('id'))
    )
    grouped = defaultdict(list)
    for row in counts_qs:
        grouped[row['activity_id']].append({
            'emoji': row['emoji'],
            'count': row['count'],
        })

    mine_map = {}
    if profile is not None and getattr(profile, 'is_authenticated', True):
        mine_map = dict(
            ActivityReaction.objects.filter(
                activity_id__in=activity_ids,
                profile=profile,
            ).values_list('activity_id', 'emoji')
        )

    for pk in activity_ids:
        result[pk] = {
            'counts': _sort_counts(grouped.get(pk, [])),
            'mine': mine_map.get(pk),
        }
    return result


def reaction_summary_for_activity(activity, profile):
    return reaction_summary_for_activities([activity.pk], profile)[activity.pk]


def toggle_reaction(activity, profile, emoji):
    """Set, change, or remove reaction. Returns summary dict for the activity."""
    if emoji not in ActivityReaction.ALLOWED_EMOJIS:
        raise ValueError('Invalid emoji')

    existing = ActivityReaction.objects.filter(activity=activity, profile=profile).first()
    if existing and existing.emoji == emoji:
        existing.delete()
    elif existing:
        existing.emoji = emoji
        existing.save(update_fields=['emoji'])
    else:
        ActivityReaction.objects.create(activity=activity, profile=profile, emoji=emoji)

    return reaction_summary_for_activity(activity, profile)
