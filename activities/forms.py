from django import forms
from django.core.exceptions import ValidationError

from activities.models import Activity, ActivityType


ALLOWED_EXTENSIONS = {'.gpx', '.fit'}


class ActivityUploadForm(forms.ModelForm):
    class Meta:
        model = Activity
        fields = ['track_file', 'title', 'description', 'activity_type']
        widgets = {
            'title': forms.TextInput(attrs={
                'class': 'w-full rounded border border-gray-300 px-3 py-2 text-sm focus:border-brand focus:outline-none focus:ring-1 focus:ring-brand',
                'placeholder': 'Название (необязательно)',
            }),
            'description': forms.Textarea(attrs={
                'class': 'w-full rounded border border-gray-300 px-3 py-2 text-sm focus:border-brand focus:outline-none focus:ring-1 focus:ring-brand',
                'rows': 3,
                'placeholder': 'Описание (необязательно)',
            }),
            'activity_type': forms.Select(attrs={
                'class': 'w-full rounded border border-gray-300 px-3 py-2 text-sm focus:border-brand focus:outline-none focus:ring-1 focus:ring-brand',
            }),
            'track_file': forms.ClearableFileInput(attrs={
                'class': 'hidden',
                'accept': '.gpx,.fit,application/gpx+xml',
                'id': 'id_track_file',
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['track_file'].required = True
        self.fields['title'].required = False
        self.fields['description'].required = False
        self.fields['activity_type'].required = False
        self.fields['activity_type'].queryset = ActivityType.objects.all()
        self.fields['activity_type'].empty_label = 'Тип активности'

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
