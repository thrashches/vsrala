from django.test import Client, TestCase
from django.urls import reverse

from profiles.models import Profile
from profiles.zones import (
    default_hr_zones,
    default_power_zones,
    estimate_lthr,
    normalize_zones,
    zone_index,
)


class ZoneDefaultsTest(TestCase):
    def test_power_zones_seven_from_ftp(self):
        zones = default_power_zones(200)
        self.assertEqual(len(zones), 7)
        self.assertEqual(zones[0]['min'], 0)
        self.assertEqual(zones[0]['max'], 110)  # 55% of 200
        self.assertEqual(zones[1]['min'], 111)
        self.assertIsNone(zones[6]['max'])
        self.assertEqual(zones[6]['min'], zones[5]['max'] + 1)

    def test_hr_zones_seven_from_max_hr(self):
        zones = default_hr_zones(190)
        lthr = estimate_lthr(190)
        self.assertEqual(lthr, 181)
        self.assertEqual(len(zones), 7)
        self.assertEqual(zones[0]['max'], int(lthr * 0.81 + 0.5))
        self.assertIsNone(zones[6]['max'])

    def test_zone_index(self):
        zones = default_power_zones(200)
        self.assertEqual(zone_index(50, zones), 0)
        self.assertEqual(zone_index(110, zones), 0)
        self.assertEqual(zone_index(111, zones), 1)
        self.assertEqual(zone_index(400, zones), 6)
        self.assertIsNone(zone_index(None, zones))

    def test_normalize_zones_rejects_bad(self):
        self.assertIsNone(normalize_zones([]))
        self.assertIsNone(normalize_zones([{'min': 0, 'max': 10}] * 6))


class ProfileZonesSettingsTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = Profile.objects.create_user(email='zones@example.com', password='testpass123')
        self.client.login(email='zones@example.com', password='testpass123')
        self.url = reverse('webinterface:settings')

    def _base_post(self, **extra):
        data = {
            'action': 'profile',
            'first_name': '',
            'email': 'zones@example.com',
            'telegram': '',
            'instagram': '',
            'vk': '',
            'is_public': 'on',
        }
        data.update(extra)
        return data

    def test_save_ftp_and_max_hr_auto_zones(self):
        response = self.client.post(self.url, self._base_post(ftp='250', max_heart_rate='190'))
        self.assertRedirects(response, self.url)
        self.user.refresh_from_db()
        self.assertEqual(self.user.ftp, 250)
        self.assertEqual(self.user.max_heart_rate, 190)
        self.assertEqual(len(self.user.power_zones), 7)
        self.assertEqual(len(self.user.hr_zones), 7)
        self.assertEqual(self.user.power_zones[0]['max'], 138)

    def test_manual_zone_edit(self):
        self.user.ftp = 200
        self.user.power_zones = default_power_zones(200)
        self.user.save()
        post = self._base_post(ftp='200', max_heart_rate='')
        for i, z in enumerate(default_power_zones(200)):
            post[f'power_zone_{i}_name'] = z['name']
            post[f'power_zone_{i}_min'] = str(z['min'] if i != 0 else 0)
            post[f'power_zone_{i}_max'] = '' if z['max'] is None else str(z['max'] if i != 0 else 99)
        # Custom Z1 upper
        post['power_zone_0_max'] = '99'
        post['power_zone_1_min'] = '100'
        response = self.client.post(self.url, post)
        self.assertRedirects(response, self.url)
        self.user.refresh_from_db()
        self.assertEqual(self.user.power_zones[0]['max'], 99)

    def test_recalculate_zones_button(self):
        self.user.ftp = 200
        self.user.power_zones = default_power_zones(200)
        self.user.power_zones[0]['max'] = 50
        self.user.save()
        post = self._base_post(ftp='200', max_heart_rate='180', recalculate_zones='1')
        for i in range(7):
            post[f'power_zone_{i}_min'] = '0'
            post[f'power_zone_{i}_max'] = '10' if i < 6 else ''
            post[f'hr_zone_{i}_min'] = '0'
            post[f'hr_zone_{i}_max'] = '10' if i < 6 else ''
        response = self.client.post(self.url, post)
        self.assertRedirects(response, self.url)
        self.user.refresh_from_db()
        self.assertEqual(self.user.power_zones[0]['max'], 110)
        self.assertEqual(len(self.user.hr_zones), 7)
