"""Samsung SmartThings Find HTTP client."""

from __future__ import annotations

import logging
from typing import Any

import aiohttp

_LOGGER = logging.getLogger(__name__)

BASE_URL = "https://smartthingsfind.samsung.com"


class SmartTagsAPIError(Exception):
    """Base exception for SmartThings Find API errors."""


class SmartTagsAuthenticationError(SmartTagsAPIError):
    """Raised when the Samsung session is no longer valid."""


class SmartTagsConnectionError(SmartTagsAPIError):
    """Raised when SmartThings Find cannot be reached or returns invalid data."""


class SmartTagsAPI:
    """Small async client for the SmartThings Find web endpoints used by the integration."""

    def __init__(self, session: aiohttp.ClientSession, jsession_id: str, region: str) -> None:
        self.session = session
        self.jsession_id = jsession_id
        self.region = region
        self.csrf_token: str | None = None

    @property
    def headers(self) -> dict[str, str]:
        """Build the browser-like headers required by the SmartThings Find web API."""
        return {
            "accept": "application/json, text/plain, */*",
            "accept-language": "en-US,en;q=0.9,he;q=0.8,ja;q=0.7",
            "Cookie": f"JSESSIONID={self.jsession_id}",
            "origin": BASE_URL,
            "priority": "u=1, i",
            "referer": f"{BASE_URL}/",
            "sec-ch-ua": '"Chromium";v="148", "Google Chrome";v="148", "Not/A)Brand";v="99"',
            "sec-ch-ua-mobile": "?0",
            "sec-ch-ua-platform": '"Windows"',
            "sec-fetch-dest": "empty",
            "sec-fetch-mode": "cors",
            "sec-fetch-site": "same-origin",
            "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/148.0.0.0 Safari/537.36",
            # Samsung's website currently sends this misspelled header. Sending
            # the correctly-spelled variant as well can change the response and
            # prevent chkLogin.do from returning the CSRF header.
            "x-fmm-orgin": self.region,
        }

    async def _request_json(
        self,
        method: str,
        path: str,
        *,
        json: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Perform a JSON request with consistent authentication and error handling."""
        headers = self.headers
        if json is not None:
            headers = {**headers, "content-type": "application/json"}

        try:
            async with self.session.request(
                method,
                f"{BASE_URL}{path}",
                headers=headers,
                json=json,
            ) as response:
                if response.status in (401, 403):
                    raise SmartTagsAuthenticationError(
                        "Samsung rejected the current JSESSIONID"
                    )
                if response.status == 429:
                    raise SmartTagsConnectionError("Samsung rate-limited the request")
                if response.status >= 400:
                    raise SmartTagsConnectionError(
                        f"Samsung returned HTTP {response.status} for {path}"
                    )

                try:
                    data = await response.json()
                except (aiohttp.ContentTypeError, ValueError) as err:
                    raise SmartTagsConnectionError(
                        f"Samsung returned an invalid JSON response for {path}"
                    ) from err

                if not isinstance(data, dict):
                    raise SmartTagsConnectionError(
                        f"Samsung returned an unexpected response for {path}"
                    )
                return data
        except SmartTagsAPIError:
            raise
        except (aiohttp.ClientError, TimeoutError) as err:
            raise SmartTagsConnectionError(
                f"Network error while contacting SmartThings Find: {err}"
            ) from err

    async def refresh_csrf_token(self) -> str:
        """Fetch and store a fresh CSRF token."""
        try:
            async with self.session.get(
                f"{BASE_URL}/chkLogin.do", headers=self.headers
            ) as response:
                if response.status in (401, 403):
                    raise SmartTagsAuthenticationError(
                        "Samsung rejected the current JSESSIONID"
                    )
                if response.status >= 400:
                    raise SmartTagsConnectionError(
                        f"Samsung returned HTTP {response.status} while refreshing authentication"
                    )

                csrf = response.headers.get("_csrf") or response.headers.get(
                    "X-CSRF-TOKEN"
                )
                if not csrf:
                    # Never log the cookie or response body; header names and status
                    # are enough to diagnose region/session mismatches.
                    _LOGGER.warning(
                        "SmartThings Find authentication response did not include a CSRF token: "
                        "status=%s region=%s content_type=%s response_headers=%s",
                        response.status,
                        self.region,
                        response.headers.get("Content-Type"),
                        sorted(response.headers.keys()),
                    )
                    # chkLogin commonly returns a normal response without a CSRF header
                    # when the browser session has expired.
                    raise SmartTagsAuthenticationError(
                        "Samsung session is invalid or expired"
                    )

                self.csrf_token = csrf
                return csrf
        except SmartTagsAPIError:
            raise
        except (aiohttp.ClientError, TimeoutError) as err:
            raise SmartTagsConnectionError(
                f"Network error while refreshing SmartThings Find authentication: {err}"
            ) from err

    async def get_devices(self) -> list[dict[str, Any]]:
        """Fetch all devices registered in the Samsung account."""
        if not self.csrf_token:
            raise SmartTagsAuthenticationError("CSRF token is not initialized")

        data = await self._request_json(
            "POST",
            f"/device/getDeviceList.do?_csrf={self.csrf_token}",
            json={},
        )
        devices = data.get("deviceList", [])
        if not isinstance(devices, list):
            raise SmartTagsConnectionError("Samsung returned an invalid device list")

        _LOGGER.debug("SmartThings Find returned %s devices", len(devices))
        return devices

    async def set_last_select(self, device_id: str) -> list[dict[str, Any]]:
        """Request the current state/location operations for a device."""
        if not self.csrf_token:
            raise SmartTagsAuthenticationError("CSRF token is not initialized")

        data = await self._request_json(
            "POST",
            f"/device/setLastSelect.do?_csrf={self.csrf_token}",
            json={"dvceId": device_id},
        )
        operations = data.get("operation", [])
        return operations if isinstance(operations, list) else []
