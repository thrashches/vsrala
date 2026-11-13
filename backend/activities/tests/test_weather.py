from datetime import datetime, timedelta, timezone
from decimal import Decimal
from unittest.mock import patch

import requests
from django.test import TestCase

from activities.models import Activity, WeatherForecast
from activities.weather import (
    PRECIP_PRIORITY_MM,
    attach_weather,
    build_weather_summary,
    find_nearby_forecast,
    get_or_fetch_forecast,
    request_points_for_track,
    weather_code_to_condition,
)
from profiles.models import Profile


def _hourly_payload(start: datetime, hours: int = 3, *, precip=0.0, code=0, temp=12.0):
    times = []
    temps = []
    precips = []
    clouds = []
    winds = []
    dirs = []
    codes = []
    for i in range(hours):
        t = (start + timedelta(hours=i)).strftime('%Y-%m-%dT%H:00')
        times.append(t)
        temps.append(temp + i)
        precips.append(precip)
        clouds.append(20)
        winds.append(15.0)
        dirs.append(90)
        codes.append(code)
    return {
        'hourly': {
            'time': times,
            'temperature_2m': temps,
            'precipitation': precips,
            'cloud_cover': clouds,
            'wind_speed_10m': winds,
            'wind_direction_10m': dirs,
            'weather_code': codes,
        },
    }


class RequestPointsTest(TestCase):
    def test_short_route_only_center(self):
        # ~1.1 km apart
        points = [[55.75, 37.60, 0], [55.76, 37.61, 600]]
        pts = request_points_for_track(points)
        self.assertEqual(len(pts), 1)
        self.assertAlmostEqual(pts[0][0], 55.755, places=3)

    def test_long_route_center_start_finish(self):
        # Moscow → roughly >100 km east
        start = [55.75, 37.60, 0]
        finish = [55.75, 39.50, 7200]  # ~119 km in longitude at this latitude
        mid = [55.75, 38.55, 3600]
        pts = request_points_for_track([start, mid, finish])
        self.assertEqual(len(pts), 3)
        # Center first
        self.assertAlmostEqual(pts[0][1], (37.60 + 39.50) / 2, places=2)


class WeatherCodeTest(TestCase):
    def test_clear_cloud_rain_snow(self):
        self.assertEqual(weather_code_to_condition(0), 'clear')
        self.assertEqual(weather_code_to_condition(3), 'cloud')
        self.assertEqual(weather_code_to_condition(61), 'rain')
        self.assertEqual(weather_code_to_condition(71), 'snow')


class FindNearbyForecastTest(TestCase):
    def setUp(self):
        self.start = datetime(2024, 6, 1, 10, 0, tzinfo=timezone.utc)
        self.end = self.start + timedelta(hours=2)
        self.fc = WeatherForecast.objects.create(
            lat=Decimal('55.750000'),
            lon=Decimal('37.600000'),
            period_start=self.start - timedelta(hours=1),
            period_end=self.end + timedelta(hours=1),
            hourly=[{
                'time': self.start.isoformat().replace('+00:00', 'Z'),
                'temperature_c': 18,
                'precipitation_mm': 0,
                'cloud_cover_pct': 10,
                'wind_speed_kmh': 12,
                'wind_direction_deg': 180,
                'weather_code': 0,
            }],
            status=WeatherForecast.STATUS_OK,
        )

    def test_finds_within_20km(self):
        found = find_nearby_forecast(55.76, 37.61, self.start, self.end)
        self.assertEqual(found.pk, self.fc.pk)

    def test_rejects_far_location(self):
        found = find_nearby_forecast(56.50, 38.50, self.start, self.end)
        self.assertIsNone(found)

    def test_rejects_non_overlapping_time(self):
        later = self.end + timedelta(days=1)
        found = find_nearby_forecast(55.75, 37.60, later, later + timedelta(hours=1))
        self.assertIsNone(found)


class BuildSummaryTest(TestCase):
    def test_mid_values_without_precip(self):
        timeline = [
            {
                'time': '2024-06-01T10:00:00Z',
                'temperature_c': 10,
                'precipitation_mm': 0,
                'wind_speed_kmh': 5,
                'wind_direction_deg': 0,
                'weather_code': 0,
                'condition': 'clear',
            },
            {
                'time': '2024-06-01T11:00:00Z',
                'temperature_c': 14,
                'precipitation_mm': 0,
                'wind_speed_kmh': 10,
                'wind_direction_deg': 90,
                'weather_code': 0,
                'condition': 'clear',
            },
            {
                'time': '2024-06-01T12:00:00Z',
                'temperature_c': 16,
                'precipitation_mm': 0,
                'wind_speed_kmh': 8,
                'wind_direction_deg': 100,
                'weather_code': 1,
                'condition': 'clear',
            },
        ]
        summary = build_weather_summary(timeline)
        self.assertEqual(summary['temperature_c'], 14)
        self.assertEqual(summary['condition'], 'clear')
        self.assertEqual(summary['wind_speed_kmh'], 10)

    def test_precip_priority_over_mid_clear(self):
        timeline = [
            {
                'time': '2024-06-01T10:00:00Z',
                'temperature_c': 10,
                'precipitation_mm': 1.0,
                'wind_speed_kmh': 5,
                'wind_direction_deg': 0,
                'weather_code': 61,
                'condition': 'rain',
            },
            {
                'time': '2024-06-01T11:00:00Z',
                'temperature_c': 14,
                'precipitation_mm': 0,
                'wind_speed_kmh': 10,
                'wind_direction_deg': 90,
                'weather_code': 0,
                'condition': 'clear',
            },
        ]
        summary = build_weather_summary(timeline)
        self.assertEqual(summary['condition'], 'rain')
        self.assertGreaterEqual(summary['precipitation_mm'], PRECIP_PRIORITY_MM)


class AttachWeatherTest(TestCase):
    def setUp(self):
        self.profile = Profile.objects.create_user(email='wx@example.com', password='x')
        self.start = datetime(2024, 6, 1, 10, 15, tzinfo=timezone.utc)

    def _outdoor(self, **kwargs):
        defaults = dict(
            profile=self.profile,
            started_at=self.start,
            duration=timedelta(hours=2),
            distance=12,
            is_indoor=False,
            track_points=[[55.75, 37.60, 0], [55.76, 37.61, 3600], [55.77, 37.62, 7200]],
        )
        defaults.update(kwargs)
        return Activity.objects.create(**defaults)

    def test_skips_indoor(self):
        activity = self._outdoor(is_indoor=True, track_points=[])
        self.assertFalse(attach_weather(activity))
        activity.refresh_from_db()
        self.assertFalse(activity.weather_summary)

    @patch('activities.weather._http_get')
    def test_attaches_timeline_and_summary(self, mock_get):
        mock_get.return_value = _hourly_payload(self.start.replace(minute=0), hours=4)
        activity = self._outdoor()
        self.assertTrue(attach_weather(activity))
        activity.refresh_from_db()
        self.assertTrue(activity.weather_summary)
        self.assertEqual(activity.weather_summary['condition'], 'clear')
        self.assertGreaterEqual(len(activity.weather_timeline), 2)
        self.assertEqual(activity.weather_forecasts.count(), 1)
        mock_get.assert_called()

    @patch('activities.weather._http_get')
    def test_reuses_nearby_forecast(self, mock_get):
        mock_get.return_value = _hourly_payload(self.start.replace(minute=0), hours=4)
        a1 = self._outdoor()
        self.assertTrue(attach_weather(a1))
        self.assertEqual(mock_get.call_count, 1)

        a2 = self._outdoor(
            track_points=[[55.751, 37.601, 0], [55.752, 37.602, 3600]],
        )
        self.assertTrue(attach_weather(a2))
        # No new HTTP — reuse within 20 km
        self.assertEqual(mock_get.call_count, 1)
        self.assertEqual(WeatherForecast.objects.filter(status='ok').count(), 1)

    @patch('activities.weather._http_get')
    def test_api_error_leaves_null_summary(self, mock_get):
        mock_get.side_effect = requests.ConnectionError('down')
        activity = self._outdoor()
        self.assertFalse(attach_weather(activity))
        activity.refresh_from_db()
        self.assertIsNone(activity.weather_summary)
        self.assertEqual(activity.weather_timeline, [])
        self.assertTrue(
            WeatherForecast.objects.filter(status=WeatherForecast.STATUS_ERROR).exists()
        )

    @patch('activities.weather._http_get')
    def test_get_or_fetch_returns_existing(self, mock_get):
        end = self.start + timedelta(hours=2)
        WeatherForecast.objects.create(
            lat=Decimal('55.750000'),
            lon=Decimal('37.600000'),
            period_start=self.start.replace(minute=0) - timedelta(hours=1),
            period_end=end + timedelta(hours=2),
            hourly=[{
                'time': self.start.replace(minute=0).isoformat().replace('+00:00', 'Z'),
                'temperature_c': 11,
                'precipitation_mm': 0,
                'cloud_cover_pct': 5,
                'wind_speed_kmh': 7,
                'wind_direction_deg': 45,
                'weather_code': 0,
            }],
            status=WeatherForecast.STATUS_OK,
        )
        fc = get_or_fetch_forecast(55.75, 37.60, self.start, end)
        self.assertIsNotNone(fc)
        mock_get.assert_not_called()
