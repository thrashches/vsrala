from django import template

register = template.Library()

_SLUG_ICONS = {
    'road_cycling': 'directions_bike',
    'mtb': 'directions_bike',
    'gravel': 'directions_bike',
    'track_cycling': 'directions_bike',
    'running': 'directions_run',
    'swimming': 'pool',
    'walking': 'directions_walk',
    'skiing': 'downhill_skiing',
    'rowing': 'rowing',
}


@register.inclusion_tag('includes/activity_type_label.html')
def activity_type_label(activity_type):
    if not activity_type:
        return {'show': False}
    slug = getattr(activity_type, 'slug', None) or ''
    return {
        'show': True,
        'name': activity_type.name,
        'icon': _SLUG_ICONS.get(slug, 'fitness_center'),
    }
