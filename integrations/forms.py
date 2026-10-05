from django import forms

INPUT_CLASS = (
    'w-full rounded border border-gray-300 px-3 py-2 text-sm '
    'focus:border-brand focus:outline-none focus:ring-1 focus:ring-brand'
)


class IntervalsConnectForm(forms.Form):
    api_key = forms.CharField(
        label='API-ключ',
        max_length=255,
        widget=forms.TextInput(attrs={
            'class': INPUT_CLASS,
            'placeholder': 'Ключ из настроек Intervals.icu → Developer Settings',
            'autocomplete': 'off',
        }),
    )

    def clean_api_key(self):
        return (self.cleaned_data.get('api_key') or '').strip()
