from __future__ import annotations

import base64
import json
import logging
from datetime import datetime, timezone
from typing import Any, Optional

import requests

logger = logging.getLogger(__name__)

DEFAULT_BASE_URL = 'https://personal.connectapi.garmin.com'
TOKEN_PATH = '/personalapitoken-service/personal-api/personal-api-key/token'
# Refresh when less than 1 hour remains (matches official client).
TOKEN_REFRESH_WINDOW_SECONDS = 60 * 60


class GarminApiError(Exception):
    def __init__(self, message: str, status_code: Optional[int] = None):
        super().__init__(message)
        self.status_code = status_code


def _jwt_expires_at(access_token: str) -> datetime:
    try:
        encoded_payload = access_token.split('.')[1]
        payload = json.loads(
            base64.urlsafe_b64decode(encoded_payload + '=' * (-len(encoded_payload) % 4))
        )
        return datetime.fromtimestamp(float(payload['exp']), tz=timezone.utc)
    except (IndexError, KeyError, TypeError, ValueError) as exc:
        raise GarminApiError('Ответ токена не является JWT с полем exp') from exc


def exchange_api_key_for_token(
    api_key: str,
    *,
    base_url: str = DEFAULT_BASE_URL,
    timeout: int = 30,
    session: Optional[requests.Session] = None,
) -> tuple[str, datetime]:
    """Exchange Personal API key for bearer token. Returns (token, expires_at)."""
    key = (api_key or '').strip()
    if not key:
        raise GarminApiError('API-ключ пуст')

    sess = session or requests.Session()
    url = f'{base_url.rstrip("/")}{TOKEN_PATH}'
    try:
        response = sess.post(
            url,
            headers={'Accept': '*/*', 'Authorization': f'ApiKey {key}'},
            timeout=timeout,
        )
    except requests.RequestException as exc:
        raise GarminApiError(f'Сеть: {exc}') from exc

    if not response.ok:
        detail = (response.text or response.reason or '')[:300]
        raise GarminApiError(
            f'Обмен API-ключа: HTTP {response.status_code} — {detail}',
            status_code=response.status_code,
        )

    access_token = response.text.strip()
    if not access_token:
        raise GarminApiError('Пустой bearer-токен')
    return access_token, _jwt_expires_at(access_token)


class GarminClient:
    """Thin client for Garmin Connect Personal API (bearer token)."""

    def __init__(
        self,
        access_token: str,
        *,
        base_url: str = DEFAULT_BASE_URL,
        timeout: int = 60,
        session: Optional[requests.Session] = None,
    ):
        self.base_url = base_url.rstrip('/')
        self.timeout = timeout
        self.session = session or requests.Session()
        self._access_token = access_token
        self._headers = {
            'Accept': 'application/json',
            'Authorization': f'Bearer {access_token}',
        }

    def update_bearer_token(self, access_token: str) -> None:
        self._access_token = access_token
        self._headers['Authorization'] = f'Bearer {access_token}'

    def _request(
        self,
        method: str,
        path: str,
        *,
        accept: str = 'application/json',
        **kwargs,
    ) -> requests.Response:
        url = f'{self.base_url}{path}'
        headers = {**self._headers, 'Accept': accept}
        try:
            return self.session.request(
                method, url, headers=headers, timeout=self.timeout, **kwargs,
            )
        except requests.RequestException as exc:
            raise GarminApiError(f'Сеть: {exc}') from exc

    def _raise_for_status(self, response: requests.Response, context: str) -> None:
        if response.ok:
            return
        detail = response.text[:300] if response.text else response.reason
        raise GarminApiError(
            f'{context}: HTTP {response.status_code} — {detail}',
            status_code=response.status_code,
        )

    def get(self, path: str, *, params: Optional[dict] = None) -> Any:
        response = self._request('GET', path, params=params)
        self._raise_for_status(response, path)
        if not response.content:
            return None
        return response.json()

    def get_user_profile_settings(self) -> dict[str, Any]:
        data = self.get('/userprofile-service/userprofile/settings')
        if not isinstance(data, dict):
            raise GarminApiError('Неожиданный формат профиля')
        return data

    def search_activities(
        self,
        *,
        start: int = 0,
        limit: int = 100,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> list[dict[str, Any]]:
        params: dict[str, Any] = {'start': start, 'limit': limit}
        if start_date:
            params['startDate'] = start_date
        if end_date:
            params['endDate'] = end_date
        data = self.get(
            '/activitylist-service/activities/search/activities',
            params=params,
        )
        if data is None:
            return []
        if not isinstance(data, list):
            raise GarminApiError('Неожиданный формат списка активностей')
        return data

    def get_activity(self, activity_id: str | int) -> dict[str, Any]:
        data = self.get(f'/activity-service/activity/{activity_id}')
        if not isinstance(data, dict):
            raise GarminApiError(f'Неожиданный формат активности {activity_id}')
        return data

    def download_activity(self, activity_id: str | int) -> bytes:
        response = self._request(
            'GET',
            f'/download-service/files/activity/{activity_id}',
            accept='application/zip, application/x-zip-compressed, application/octet-stream',
        )
        self._raise_for_status(response, f'Скачивание {activity_id}')
        if not response.content:
            raise GarminApiError(f'Пустой файл активности {activity_id}')
        return response.content

    def get_power_zones(self) -> Any:
        return self.get('/biometric-service/powerZones/all')

    def get_cycling_ftp(self) -> Any:
        return self.get('/biometric-service/latestFunctionalThresholdPower/CYCLING')
