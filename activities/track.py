"""Track cycling helpers: classic velodrome lap lengths and type name."""

from decimal import Decimal

TRACK_CYCLING_TYPE_NAME = 'Трековый велосипед'

TRACK_LAP_LENGTH_CHOICES = [
    (Decimal('166.66'), '166,66 м'),
    (Decimal('200'), '200 м'),
    (Decimal('250'), '250 м'),
    (Decimal('286.5'), '286,5 м'),
    (Decimal('333.33'), '333,33 м'),
    (Decimal('400'), '400 м'),
    (Decimal('450'), '450 м'),
    (Decimal('500'), '500 м'),
]

TRACK_LAP_LENGTH_VALUES = {value for value, _label in TRACK_LAP_LENGTH_CHOICES}


def format_track_lap_length(length_m) -> str:
    """Human-readable lap length, e.g. '250 м' or '333,33 м'."""
    if length_m is None:
        return ''
    value = Decimal(length_m)
    for choice_value, label in TRACK_LAP_LENGTH_CHOICES:
        if choice_value == value:
            return label
    normalized = format(value.normalize(), 'f').rstrip('0').rstrip('.')
    return f'{normalized.replace(".", ",")} м'


def is_track_cycling_type(activity_type) -> bool:
    return bool(activity_type and activity_type.name == TRACK_CYCLING_TYPE_NAME)
