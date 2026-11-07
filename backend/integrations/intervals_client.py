from __future__ import annotations

import gzip
import logging
import time
from typing import Any, Optional

import requests

logger = logging.getLogger(__name__)

BASE_URL = 'https://intervals.icu/api/v1'
_RETRYABLE_STATUS = {429, 500, 502, 503, 504}
_MAX_RETRIES = 2
_RETRY_BACKOFF_SECONDS = 1.5


class IntervalsApiError(Exception):
    def __init__(self, message: str, status_code: Optional[int] = None):
        super().__init__(message)
        self.status_code = status_code


class IntervalsClient:
    """Thin client for Intervals.icu personal API key auth."""

    def __init__(self, api_key: str, athlete_id: str = '0', timeout: int = 60):
        self.api_key = api_key
        self.athlete_id = (athlete_id or '0').strip() or '0'
        self.timeout = timeout
        self.session = requests.Session()
        self.session.auth = ('API_KEY', api_key)
        self.session.headers.update({'Accept': 'application/json'})

    def _request(self, method: str, path: str, **kwargs) -> requests.Response:
        url = f'{BASE_URL}{path}'
        last_exc: Optional[Exception] = None
        for attempt in range(_MAX_RETRIES + 1):
            try:
                response = self.session.request(method, url, timeout=self.timeout, **kwargs)
            except requests.RequestException as exc:
                last_exc = exc
                if attempt >= _MAX_RETRIES:
                    raise IntervalsApiError(f'Сеть: {exc}') from exc
                time.sleep(_RETRY_BACKOFF_SECONDS * (attempt + 1))
                continue

            if response.status_code in _RETRYABLE_STATUS and attempt < _MAX_RETRIES:
                time.sleep(_RETRY_BACKOFF_SECONDS * (attempt + 1))
                continue
            return response

        raise IntervalsApiError(f'Сеть: {last_exc}')

    def _raise_for_status(self, response: requests.Response, context: str) -> None:
        if response.ok:
            return
        detail = response.text[:300] if response.text else response.reason
        raise IntervalsApiError(
            f'{context}: HTTP {response.status_code} — {detail}',
            status_code=response.status_code,
        )

    def get_athlete(self) -> dict[str, Any]:
        response = self._request('GET', f'/athlete/{self.athlete_id}')
        self._raise_for_status(response, 'Проверка API-ключа')
        return response.json()

    def list_activities(self, oldest: str, newest: str) -> list[dict[str, Any]]:
        response = self._request(
            'GET',
            f'/athlete/{self.athlete_id}/activities',
            params={'oldest': oldest, 'newest': newest},
        )
        self._raise_for_status(response, 'Список активностей')
        data = response.json()
        if not isinstance(data, list):
            raise IntervalsApiError('Неожиданный формат списка активностей')
        return data

    def list_wellness(self, oldest: str, newest: str) -> list[dict[str, Any]]:
        response = self._request(
            'GET',
            f'/athlete/{self.athlete_id}/wellness',
            params={'oldest': oldest, 'newest': newest},
        )
        self._raise_for_status(response, 'Wellness')
        data = response.json()
        if data is None:
            return []
        if not isinstance(data, list):
            raise IntervalsApiError('Неожиданный формат wellness')
        return data

    def get_sport_settings(self) -> list[dict[str, Any]]:
        response = self._request('GET', f'/athlete/{self.athlete_id}/sport-settings')
        self._raise_for_status(response, 'Sport settings')
        data = response.json()
        if data is None:
            return []
        if isinstance(data, dict):
            return [data]
        if not isinstance(data, list):
            raise IntervalsApiError('Неожиданный формат sport-settings')
        return data

    def download_original_file(self, activity_id: str) -> bytes:
        """Download original activity file (gzip-compressed) and decompress."""
        response = self._request('GET', f'/activity/{activity_id}/file')
        self._raise_for_status(response, f'Скачивание файла {activity_id}')
        return _maybe_gunzip(response.content)

    def download_fit_file(self, activity_id: str) -> bytes:
        """Download Intervals.icu-generated FIT file (gzip-compressed)."""
        response = self._request('GET', f'/activity/{activity_id}/fit-file')
        self._raise_for_status(response, f'Скачивание FIT {activity_id}')
        return _maybe_gunzip(response.content)


def _maybe_gunzip(payload: bytes) -> bytes:
    if len(payload) >= 2 and payload[0] == 0x1F and payload[1] == 0x8B:
        try:
            return gzip.decompress(payload)
        except OSError as exc:
            raise IntervalsApiError(f'Не удалось распаковать gzip: {exc}') from exc
    return payload
