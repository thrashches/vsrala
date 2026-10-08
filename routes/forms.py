from django import forms
from django.core.exceptions import ValidationError

from .models import Route

INPUT_CLASS = (
    'w-full rounded border border-gray-300 px-3 py-2 text-sm '
    'focus:border-brand focus:outline-none focus:ring-1 focus:ring-brand'
)

ALLOWED_EXTENSIONS = {'.gpx'}


class RouteUploadForm(forms.ModelForm):
    class Meta:
        model = Route
        fields = ['source_gpx', 'title', 'description', 'visibility']
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
            'visibility': forms.Select(attrs={'class': INPUT_CLASS}),
            'source_gpx': forms.ClearableFileInput(attrs={
                'class': 'hidden',
                'accept': '.gpx,application/gpx+xml',
                'id': 'id_source_gpx',
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['source_gpx'].required = True
        self.fields['source_gpx'].label = 'GPX-файл'
        self.fields['title'].required = False
        self.fields['description'].required = False

    def clean_source_gpx(self):
        f = self.cleaned_data.get('source_gpx')
        if not f:
            raise ValidationError('Выберите файл .gpx')
        name = f.name.lower()
        if not any(name.endswith(ext) for ext in ALLOWED_EXTENSIONS):
            raise ValidationError('Поддерживаются только файлы .gpx')
        if f.size > 50 * 1024 * 1024:
            raise ValidationError('Файл слишком большой (макс. 50 МБ)')
        return f


class RouteMetaForm(forms.ModelForm):
    class Meta:
        model = Route
        fields = ['title', 'description', 'visibility']
        widgets = {
            'title': forms.TextInput(attrs={'class': INPUT_CLASS}),
            'description': forms.Textarea(attrs={'class': INPUT_CLASS, 'rows': 3}),
            'visibility': forms.Select(attrs={'class': INPUT_CLASS}),
        }


class RouteFromActivityForm(forms.Form):
    title = forms.CharField(
        required=False,
        max_length=255,
        widget=forms.TextInput(attrs={'class': INPUT_CLASS, 'placeholder': 'Название'}),
    )
    description = forms.CharField(
        required=False,
        max_length=3000,
        widget=forms.Textarea(attrs={'class': INPUT_CLASS, 'rows': 3}),
    )
    visibility = forms.ChoiceField(
        choices=Route.Visibility.choices,
        initial=Route.Visibility.PRIVATE,
        widget=forms.Select(attrs={'class': INPUT_CLASS}),
    )
    start_idx = forms.IntegerField(min_value=0, widget=forms.HiddenInput())
    end_idx = forms.IntegerField(min_value=0, widget=forms.HiddenInput())

    def clean(self):
        cleaned = super().clean()
        start = cleaned.get('start_idx')
        end = cleaned.get('end_idx')
        if start is not None and end is not None and end < start:
            cleaned['start_idx'], cleaned['end_idx'] = end, start
        return cleaned
