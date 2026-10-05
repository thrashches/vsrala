from django import forms
from django.contrib.auth.forms import PasswordChangeForm as DjangoPasswordChangeForm
from django.core.exceptions import ValidationError

from profiles.models import Profile
from profiles.zones import (
    HR_ZONE_NAMES,
    POWER_ZONE_NAMES,
    default_hr_zones,
    default_power_zones,
    normalize_zones,
)

INPUT_CLASS = (
    'w-full rounded border border-gray-300 px-3 py-2 text-sm '
    'focus:border-brand focus:outline-none focus:ring-1 focus:ring-brand'
)

ZONE_INPUT_CLASS = (
    'w-20 rounded border border-gray-300 px-2 py-1 text-sm text-center '
    'focus:border-brand focus:outline-none focus:ring-1 focus:ring-brand'
)

ALLOWED_IMAGE_TYPES = {'image/jpeg', 'image/png', 'image/gif', 'image/webp'}
MAX_PHOTO_SIZE = 5 * 1024 * 1024


def _parse_zone_post(data, prefix: str, names: tuple[str, ...]) -> list[dict] | None:
    """Parse hr_zone_N_min/max or power_zone_N_min/max from POST. None if absent."""
    if f'{prefix}_0_min' not in data:
        return None
    raw = []
    for i in range(7):
        lo = data.get(f'{prefix}_{i}_min', '')
        hi = data.get(f'{prefix}_{i}_max', '')
        name = data.get(f'{prefix}_{i}_name', names[i])
        raw.append({
            'name': name or names[i],
            'min': lo,
            'max': hi if hi != '' else None,
        })
    return raw


class ProfileSettingsForm(forms.ModelForm):
    class Meta:
        model = Profile
        fields = [
            'photo', 'first_name', 'email', 'telegram', 'instagram', 'vk',
            'ftp', 'max_heart_rate', 'is_public',
        ]
        widgets = {
            'photo': forms.FileInput(attrs={
                'class': 'hidden',
                'accept': 'image/jpeg,image/png,image/gif,image/webp',
                'id': 'id_photo',
            }),
            'first_name': forms.TextInput(attrs={
                'class': INPUT_CLASS,
                'placeholder': 'Как вас показывать в ленте',
                'autocomplete': 'nickname',
            }),
            'email': forms.EmailInput(attrs={
                'class': INPUT_CLASS,
                'autocomplete': 'email',
            }),
            'telegram': forms.TextInput(attrs={
                'class': INPUT_CLASS,
                'placeholder': '@username или ссылка',
            }),
            'instagram': forms.TextInput(attrs={
                'class': INPUT_CLASS,
                'placeholder': '@username или ссылка',
            }),
            'vk': forms.TextInput(attrs={
                'class': INPUT_CLASS,
                'placeholder': 'id или ссылка',
            }),
            'ftp': forms.NumberInput(attrs={
                'class': INPUT_CLASS,
                'placeholder': 'Вт',
                'min': 1,
                'max': 999,
            }),
            'max_heart_rate': forms.NumberInput(attrs={
                'class': INPUT_CLASS,
                'placeholder': 'уд/мин',
                'min': 100,
                'max': 250,
            }),
            'is_public': forms.CheckboxInput(attrs={
                'class': 'h-4 w-4 rounded border-gray-300 text-brand focus:ring-brand',
            }),
        }
        labels = {
            'photo': 'Аватар',
            'first_name': 'Отображаемое имя',
            'email': 'Почта',
            'telegram': 'Telegram',
            'instagram': 'Instagram',
            'vk': 'VK',
            'ftp': 'FTP (Вт)',
            'max_heart_rate': 'Макс. пульс (уд/мин)',
            'is_public': 'Открытый профиль',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['photo'].required = False
        self.fields['first_name'].required = False
        self.fields['telegram'].required = False
        self.fields['instagram'].required = False
        self.fields['vk'].required = False
        self.fields['ftp'].required = False
        self.fields['max_heart_rate'].required = False
        self.power_zones_for_display = self._zones_for_display('power')
        self.hr_zones_for_display = self._zones_for_display('hr')
        self.zone_input_class = ZONE_INPUT_CLASS

    def _zones_for_display(self, kind: str):
        instance = self.instance
        if kind == 'power':
            stored = normalize_zones(getattr(instance, 'power_zones', None), names=POWER_ZONE_NAMES)
            if stored:
                return stored
            if instance.ftp:
                return default_power_zones(instance.ftp)
            return [
                {'name': POWER_ZONE_NAMES[i], 'min': '', 'max': '' if i < 6 else None}
                for i in range(7)
            ]
        stored = normalize_zones(getattr(instance, 'hr_zones', None), names=HR_ZONE_NAMES)
        if stored:
            return stored
        if instance.max_heart_rate:
            return default_hr_zones(instance.max_heart_rate)
        return [
            {'name': HR_ZONE_NAMES[i], 'min': '', 'max': '' if i < 6 else None}
            for i in range(7)
        ]

    def clean_first_name(self):
        return (self.cleaned_data.get('first_name') or '').strip()

    def clean_email(self):
        email = Profile.objects.normalize_email(self.cleaned_data['email'])
        qs = Profile.objects.filter(email__iexact=email)
        if self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise ValidationError('Пользователь с такой почтой уже существует')
        return email

    def clean_photo(self):
        photo = self.cleaned_data.get('photo')
        if not photo:
            return self.instance.photo
        if hasattr(photo, 'content_type') and photo.content_type not in ALLOWED_IMAGE_TYPES:
            raise ValidationError('Поддерживаются JPEG, PNG, GIF и WebP')
        if photo.size > MAX_PHOTO_SIZE:
            raise ValidationError('Файл слишком большой (макс. 5 МБ)')
        return photo

    def clean_ftp(self):
        ftp = self.cleaned_data.get('ftp')
        if ftp is not None and ftp <= 0:
            raise ValidationError('FTP должен быть больше 0')
        return ftp

    def clean_max_heart_rate(self):
        max_hr = self.cleaned_data.get('max_heart_rate')
        if max_hr is not None and (max_hr < 100 or max_hr > 250):
            raise ValidationError('Укажите пульс от 100 до 250')
        return max_hr

    def clean(self):
        cleaned = super().clean()
        data = self.data
        recalculate = bool(data.get('recalculate_zones'))

        ftp = cleaned.get('ftp')
        max_hr = cleaned.get('max_heart_rate')
        old_ftp = self.instance.ftp
        old_max_hr = self.instance.max_heart_rate

        power_raw = _parse_zone_post(data, 'power_zone', POWER_ZONE_NAMES)
        hr_raw = _parse_zone_post(data, 'hr_zone', HR_ZONE_NAMES)

        if recalculate:
            cleaned['power_zones'] = default_power_zones(ftp) if ftp else []
            cleaned['hr_zones'] = default_hr_zones(max_hr) if max_hr else []
            if cleaned['power_zones']:
                self.power_zones_for_display = cleaned['power_zones']
            if cleaned['hr_zones']:
                self.hr_zones_for_display = cleaned['hr_zones']
            return cleaned

        ftp_changed = ftp != old_ftp
        max_hr_changed = max_hr != old_max_hr

        if power_raw is not None and not ftp_changed:
            zones = normalize_zones(power_raw, names=POWER_ZONE_NAMES)
            if zones is None and any(
                data.get(f'power_zone_{i}_min') not in (None, '') for i in range(7)
            ):
                raise ValidationError('Некорректные зоны мощности')
            cleaned['power_zones'] = zones or []
        elif ftp_changed:
            cleaned['power_zones'] = default_power_zones(ftp) if ftp else []
        else:
            cleaned['power_zones'] = self.instance.power_zones or []

        if hr_raw is not None and not max_hr_changed:
            zones = normalize_zones(hr_raw, names=HR_ZONE_NAMES)
            if zones is None and any(
                data.get(f'hr_zone_{i}_min') not in (None, '') for i in range(7)
            ):
                raise ValidationError('Некорректные зоны пульса')
            cleaned['hr_zones'] = zones or []
        elif max_hr_changed:
            cleaned['hr_zones'] = default_hr_zones(max_hr) if max_hr else []
        else:
            cleaned['hr_zones'] = self.instance.hr_zones or []

        # Refresh display lists after validation for re-render
        if 'power_zones' in cleaned and cleaned['power_zones']:
            self.power_zones_for_display = cleaned['power_zones']
        if 'hr_zones' in cleaned and cleaned['hr_zones']:
            self.hr_zones_for_display = cleaned['hr_zones']

        return cleaned

    def save(self, commit=True):
        instance = super().save(commit=False)
        instance.power_zones = self.cleaned_data.get('power_zones') or []
        instance.hr_zones = self.cleaned_data.get('hr_zones') or []
        if commit:
            instance.save()
        return instance


class PasswordChangeForm(DjangoPasswordChangeForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['old_password'].label = 'Текущий пароль'
        self.fields['new_password1'].label = 'Новый пароль'
        self.fields['new_password2'].label = 'Повтор нового пароля'
        for name in ('old_password', 'new_password1', 'new_password2'):
            self.fields[name].widget.attrs.update({
                'class': INPUT_CLASS,
                'autocomplete': 'new-password' if name != 'old_password' else 'current-password',
            })


class DeleteAccountForm(forms.Form):
    password = forms.CharField(
        label='Пароль',
        strip=False,
        widget=forms.PasswordInput(attrs={
            'class': INPUT_CLASS,
            'autocomplete': 'current-password',
            'placeholder': 'Введите пароль для подтверждения',
        }),
    )

    def __init__(self, user, *args, **kwargs):
        self.user = user
        super().__init__(*args, **kwargs)

    def clean_password(self):
        password = self.cleaned_data['password']
        if not self.user.check_password(password):
            raise ValidationError('Неверный пароль')
        return password
