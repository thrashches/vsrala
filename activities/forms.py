from django import forms
from django.core.exceptions import ValidationError

from activities.models import Activity, ActivityType
from activities.track import TRACK_CYCLING_TYPE_NAME, is_track_cycling_type


ALLOWED_EXTENSIONS = {'.gpx', '.fit'}

INPUT_CLASS = (
    'w-full rounded border border-gray-300 px-3 py-2 text-sm '
    'focus:border-brand focus:outline-none focus:ring-1 focus:ring-brand'
)
CHECKBOX_CLASS = 'h-4 w-4 rounded border-gray-300 text-brand focus:ring-brand'


def _configure_track_fields(form, *, user=None, initial_from_user=False):
    form.fields['is_track'].required = False
    form.fields['track_lap_length_m'].required = False
    lap_field = form.fields['track_lap_length_m']
    lap_choices = [
        (value, label) for value, label in lap_field.choices if value != ''
    ]
    lap_field.choices = [('', 'Выберите длину круга')] + lap_choices

    if initial_from_user and user is not None and not form.is_bound:
        if getattr(user, 'trains_on_track', False):
            form.fields['is_track'].initial = True
            if user.default_track_lap_length_m is not None:
                form.fields['track_lap_length_m'].initial = user.default_track_lap_length_m


def _clean_track_fields(cleaned, *, activity_type=None):
    is_track = cleaned.get('is_track')
    if is_track_cycling_type(activity_type):
        is_track = True
        cleaned['is_track'] = True

    lap_length = cleaned.get('track_lap_length_m')
    if is_track and lap_length is None:
        raise ValidationError({
            'track_lap_length_m': 'Укажите длину круга для тренировки на треке',
        })
    if not is_track:
        cleaned['track_lap_length_m'] = None
    return cleaned


class ActivityUploadForm(forms.ModelForm):
    class Meta:
        model = Activity
        fields = [
            'track_file', 'title', 'description', 'activity_type',
            'is_track', 'track_lap_length_m',
        ]
        widgets = {
            'title': forms.TextInput(attrs={
                'class': INPUT_CLASS,
                'placeholder': 'Название (необязательно)',
            }),
            'description': forms.Textarea(attrs={
                'class': INPUT_CLASS,
                'rows': 3,
                'placeholder': 'Описание (необязательно)',
            }),
            'activity_type': forms.Select(attrs={
                'class': INPUT_CLASS,
                'id': 'id_activity_type',
            }),
            'track_file': forms.ClearableFileInput(attrs={
                'class': 'hidden',
                'accept': '.gpx,.fit,application/gpx+xml',
                'id': 'id_track_file',
            }),
            'is_track': forms.CheckboxInput(attrs={
                'class': CHECKBOX_CLASS,
                'id': 'id_is_track',
            }),
            'track_lap_length_m': forms.Select(attrs={
                'class': INPUT_CLASS,
                'id': 'id_track_lap_length_m',
            }),
        }

    def __init__(self, *args, user=None, **kwargs):
        self.user = user
        super().__init__(*args, **kwargs)
        self.fields['track_file'].required = True
        self.fields['title'].required = False
        self.fields['description'].required = False
        self.fields['activity_type'].required = False
        self.fields['activity_type'].queryset = ActivityType.objects.all()
        self.fields['activity_type'].empty_label = 'Тип активности'
        _configure_track_fields(self, user=user, initial_from_user=True)
        self.track_cycling_type_id = (
            ActivityType.objects.filter(name=TRACK_CYCLING_TYPE_NAME)
            .values_list('pk', flat=True)
            .first()
        )
        self.default_track_lap_length = (
            str(user.default_track_lap_length_m)
            if user and user.default_track_lap_length_m is not None
            else ''
        )

    def clean_track_file(self):
        track_file = self.cleaned_data.get('track_file')
        if not track_file:
            raise ValidationError('Выберите файл .gpx или .fit')
        name = track_file.name.lower()
        if not any(name.endswith(ext) for ext in ALLOWED_EXTENSIONS):
            raise ValidationError('Поддерживаются только файлы .gpx и .fit')
        if track_file.size > 50 * 1024 * 1024:
            raise ValidationError('Файл слишком большой (макс. 50 МБ)')
        return track_file

    def clean(self):
        cleaned = super().clean()
        return _clean_track_fields(
            cleaned,
            activity_type=cleaned.get('activity_type'),
        )


class ActivityEditForm(forms.ModelForm):
    class Meta:
        model = Activity
        fields = [
            'title', 'description', 'activity_type',
            'is_track', 'track_lap_length_m',
        ]
        widgets = {
            'title': forms.TextInput(attrs={
                'class': INPUT_CLASS,
                'placeholder': 'Название (необязательно)',
            }),
            'description': forms.Textarea(attrs={
                'class': INPUT_CLASS,
                'rows': 3,
                'placeholder': 'Описание (необязательно)',
            }),
            'activity_type': forms.Select(attrs={
                'class': INPUT_CLASS,
                'id': 'id_activity_type',
            }),
            'is_track': forms.CheckboxInput(attrs={
                'class': CHECKBOX_CLASS,
                'id': 'id_is_track',
            }),
            'track_lap_length_m': forms.Select(attrs={
                'class': INPUT_CLASS,
                'id': 'id_track_lap_length_m',
            }),
        }

    def __init__(self, *args, user=None, **kwargs):
        self.user = user
        super().__init__(*args, **kwargs)
        self.fields['title'].required = False
        self.fields['description'].required = False
        self.fields['activity_type'].required = False
        self.fields['activity_type'].queryset = ActivityType.objects.all()
        self.fields['activity_type'].empty_label = 'Тип активности'
        _configure_track_fields(self, user=user, initial_from_user=False)
        self.track_cycling_type_id = (
            ActivityType.objects.filter(name=TRACK_CYCLING_TYPE_NAME)
            .values_list('pk', flat=True)
            .first()
        )
        default_user = user or getattr(self.instance, 'profile', None)
        self.default_track_lap_length = (
            str(default_user.default_track_lap_length_m)
            if default_user and default_user.default_track_lap_length_m is not None
            else ''
        )

    def clean(self):
        cleaned = super().clean()
        return _clean_track_fields(
            cleaned,
            activity_type=cleaned.get('activity_type'),
        )
