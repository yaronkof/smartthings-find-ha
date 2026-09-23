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

    def __init__(
        self,
        session: aiohttp.ClientSession,
        jsession_id: str,
        region: str,
        cookie_header: str | None = None,
    ) -> None:
        self.session = session
        self.jsession_id = jsession_id
        self.cookie_header = cookie_header.strip() if cookie_header else None
        self.region = region
        self.csrf_token: str | None = None
        self._use_correct_origin_header = False
        self._browser_compat_mode = False

    @property
    def headers(self) -> dict[str, str]:
        """Build the browser-like headers required by the SmartThings Find web API."""
        headers = {
            "accept": "application/json, text/plain, */*",
            "accept-language": (
                "en-GB,en;q=0.9"
                if self._browser_compat_mode
                else "en-US,en;q=0.9,he;q=0.8,ja;q=0.7"
            ),
            "Cookie": self.cookie_header or f"JSESSIONID={self.jsession_id}",
            "origin": BASE_URL,
            "priority": "u=1, i",
            "referer": f"{BASE_URL}/",
            "sec-fetch-dest": "empty",
            "sec-fetch-mode": "cors",
            "sec-fetch-site": "same-origin",
            "user-agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:156.0) "
                "Gecko/20100101 Firefox/156.0"
                if self._browser_compat_mode
                else "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/148.0.0.0 Safari/537.36"
            ),
            # The legacy path sends Samsung's misspelled request header. In
            # browser-compatible mode the browser sends neither spelling; the
            # x-fmm-orgin value seen in DevTools is a response header.
            **(
                {}
                if self._browser_compat_mode
                else {"x-fmm-orgin": self.region}
            ),
        }
        if not self._browser_compat_mode:
            headers.update({
                "sec-ch-ua": '"Chromium";v="148", "Google Chrome";v="148", "Not/A)Brand";v="99"',
                "sec-ch-ua-mobile": "?0",
                "sec-ch-ua-platform": '"Windows"',
            })
        else:
            headers.pop("origin", None)
            headers.pop("priority", None)
        if self._use_correct_origin_header:
            # Compatibility fallback for older/server variants that expect the
            # correctly-spelled header as well.
            headers["x-fmm-origin"] = self.region
        return headers

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
        """Fetch and store a fresh CSRF token with a compatible header fallback."""
        try:
            response_details: tuple[
                str, int, str | None, list[str], list[str], list[str], int
            ] | None = None
            for attempt_name, use_correct_header, browser_compat_mode in (
                ("legacy", False, False),
                ("correct_origin", True, False),
                ("browser_compatible", False, True),
            ):
                self._use_correct_origin_header = use_correct_header
                self._browser_compat_mode = browser_compat_mode
                request_headers = self.headers
                cookie_names = sorted(
                    name.strip()
                    for name, separator, _value in (
                        cookie.partition("=")
                        for cookie in request_headers.get("Cookie", "").split(";")
                    )
                    if separator and name.strip()
                )
                _LOGGER.debug(
                    "SmartThings Find CSRF attempt=%s request_headers=%s cookie_names=%s",
                    attempt_name,
                    sorted(request_headers.keys()),
                    cookie_names,
                )
                async with self.session.get(
                    f"{BASE_URL}/chkLogin.do", headers=request_headers
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
                    if csrf:
                        self.csrf_token = csrf
                        return csrf

                    response_details = (
                        attempt_name,
                        response.status,
                        response.headers.get("Content-Type"),
                        sorted(response.headers.keys()),
                        sorted(request_headers.keys()),
                        cookie_names,
                        len(await response.read()),
                    )
                    _LOGGER.debug(
                        "SmartThings Find CSRF attempt=%s returned no token: "
                        "status=%s content_type=%s body_length=%s",
                        attempt_name,
                        response.status,
                        response.headers.get("Content-Type"),
                        response_details[-1],
                    )

            # Never log the cookie or response body; header names and status are
            # enough to diagnose region/session mismatches.
            (
                attempt_name,
                status,
                content_type,
                response_headers,
                request_headers,
                cookie_names,
                body_length,
            ) = response_details or (
                "none",
                0,
                None,
                [],
                [],
                [],
                0,
            )
            _LOGGER.warning(
                "SmartThings Find authentication response did not include a CSRF token: "
                "attempt=%s status=%s region=%s content_type=%s body_length=%s "
                "request_headers=%s cookie_names=%s response_headers=%s",
                attempt_name,
                status,
                self.region,
                content_type,
                body_length,
                request_headers,
                cookie_names,
                response_headers,
            )
            raise SmartTagsAuthenticationError("Samsung session is invalid or expired")
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
