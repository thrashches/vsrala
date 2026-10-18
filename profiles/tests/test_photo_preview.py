from io import BytesIO
from unittest.mock import patch

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from PIL import Image

from profiles.forms import ProfileSettingsForm
from profiles.models import Profile
from profiles.photo_preview import apply_photo_preview
from profiles.tasks import generate_photo_previews_for_profiles


def _make_image_upload(name: str, fmt: str = 'JPEG', size=(400, 300), content_type: str | None = None):
    buf = BytesIO()
    Image.new('RGB', size, color=(200, 80, 40)).save(buf, format=fmt)
    data = buf.getvalue()
    if content_type is None:
        content_type = {
            'JPEG': 'image/jpeg',
            'PNG': 'image/png',
            'WEBP': 'image/webp',
            'GIF': 'image/gif',
        }.get(fmt, 'application/octet-stream')
    return SimpleUploadedFile(name, data, content_type=content_type)


@override_settings(MEDIA_ROOT='/tmp/vsrala_test_media_photo_preview')
class PhotoPreviewFormTest(TestCase):
    def setUp(self):
        self.profile = Profile.objects.create_user(
            email='avatar@example.com',
            password='testpass123',
        )

    def _save_photo(self, upload):
        form = ProfileSettingsForm(
            data={
                'first_name': 'Test',
                'email': self.profile.email,
                'telegram': '',
                'instagram': '',
                'vk': '',
                'ftp': '',
                'max_heart_rate': '',
                'is_public': 'on',
            },
            files={'photo': upload},
            instance=self.profile,
        )
        self.assertTrue(form.is_valid(), form.errors)
        return form.save()

    def test_jpg_upload_creates_webp_preview(self):
        profile = self._save_photo(_make_image_upload('avatar.jpg', 'JPEG'))
        profile.refresh_from_db()
        self.assertTrue(profile.photo.name)
        self.assertFalse(profile.photo.name.endswith('.webp'))
        self.assertTrue(profile.photo_preview.name.endswith('.webp'))
        self.assertEqual(profile.avatar_url, profile.photo_preview.url)

    def test_jpeg_extension_accepted(self):
        profile = self._save_photo(_make_image_upload('avatar.jpeg', 'JPEG'))
        profile.refresh_from_db()
        self.assertTrue(profile.photo_preview.name.endswith('.webp'))

    def test_rejects_unsupported_extension(self):
        upload = SimpleUploadedFile('avatar.bmp', b'not-an-image', content_type='image/bmp')
        form = ProfileSettingsForm(
            data={
                'first_name': 'Test',
                'email': self.profile.email,
                'telegram': '',
                'instagram': '',
                'vk': '',
                'ftp': '',
                'max_heart_rate': '',
                'is_public': 'on',
            },
            files={'photo': upload},
            instance=self.profile,
        )
        self.assertFalse(form.is_valid())
        self.assertIn('photo', form.errors)

    def test_accepts_image_jpg_mime(self):
        profile = self._save_photo(
            _make_image_upload('avatar.jpg', 'JPEG', content_type='image/jpg'),
        )
        profile.refresh_from_db()
        self.assertTrue(profile.photo_preview)


@override_settings(MEDIA_ROOT='/tmp/vsrala_test_media_photo_preview')
class PhotoPreviewTaskAdminTest(TestCase):
    def setUp(self):
        self.admin = Profile.objects.create_superuser(
            email='admin-avatar@example.com',
            password='testpass123',
        )
        self.profile = Profile.objects.create_user(
            email='owner-avatar@example.com',
            password='x',
        )
        upload = _make_image_upload('orig.jpg')
        self.profile.photo.save('orig.jpg', upload, save=True)
        self.client = Client()
        self.client.login(email='admin-avatar@example.com', password='testpass123')

    def test_task_generates_previews(self):
        result = generate_photo_previews_for_profiles([self.profile.pk])
        self.assertEqual(result['generated'], 1)
        self.profile.refresh_from_db()
        self.assertTrue(self.profile.photo_preview.name.endswith('.webp'))

    def test_apply_photo_preview_skips_without_photo(self):
        empty = Profile.objects.create_user(email='empty-avatar@example.com', password='x')
        self.assertFalse(apply_photo_preview(empty))

    @patch('profiles.admin.generate_photo_previews_for_profiles.delay')
    def test_admin_action_enqueues_task(self, delay):
        url = reverse('admin:profiles_profile_changelist')
        response = self.client.post(url, {
            'action': 'enqueue_photo_preview_generation',
            '_selected_action': [str(self.profile.pk)],
        })
        self.assertEqual(response.status_code, 302)
        delay.assert_called_once()
        self.assertEqual(delay.call_args.args[0], [self.profile.pk])
