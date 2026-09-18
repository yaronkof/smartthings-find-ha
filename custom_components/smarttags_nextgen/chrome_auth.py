"""Optional headed Chrome bootstrap for a user-owned Samsung web session.

This deliberately uses ordinary Selenium and a persistent Chrome profile. It
does not add stealth flags, patch browser fingerprints, solve challenges, or
retry authentication. The user completes Samsung login in the visible browser;
the integration only reads the JSESSIONID cookie for the exact SmartThings Find
host and then closes the browser.
"""

from __future__ import annotations

import time
from pathlib import Path

from .api import BASE_URL

CHROME_LOGIN_TIMEOUT = 300


class ChromeAuthError(Exception):
    """Raised when the headed Chrome bootstrap cannot complete."""


def get_jsession_id_from_chrome(
    profile_dir: str, *, chrome_binary: str | None = None
) -> str:
    """Open one headed persistent-profile session and wait for manual login.

    The profile directory is created if needed and is never deleted. Chrome's
    own profile lock prevents two simultaneous bootstrap sessions from sharing
    it; this function does not terminate existing browser processes.
    """
    try:
        from selenium import webdriver
        from selenium.common.exceptions import WebDriverException
    except ImportError as err:  # pragma: no cover - dependency/runtime branch
        raise ChromeAuthError("Selenium is not installed") from err

    profile = Path(profile_dir).expanduser()
    profile.mkdir(parents=True, exist_ok=True)
    options = webdriver.ChromeOptions()
    options.add_argument(f"--user-data-dir={profile}")
    options.add_argument("--profile-directory=Default")
    if chrome_binary:
        options.binary_location = chrome_binary

    driver = None
    try:
        # Selenium Manager resolves a normal compatible ChromeDriver. No
        # undetected/stealth driver or anti-detection option is used.
        driver = webdriver.Chrome(options=options)
        driver.get(BASE_URL + "/")
        deadline = time.monotonic() + CHROME_LOGIN_TIMEOUT
        while time.monotonic() < deadline:
            for cookie in driver.get_cookies():
                if cookie.get("name") != "JSESSIONID":
                    continue
                domain = str(cookie.get("domain", "")).lstrip(".").lower()
                if domain and domain != "smartthingsfind.samsung.com":
                    continue
                value = cookie.get("value")
                if isinstance(value, str) and value.strip():
                    return value.strip()
            time.sleep(1)
        raise ChromeAuthError(
            "No SmartThings Find JSESSIONID was received before the login timeout"
        )
    except ChromeAuthError:
        raise
    except WebDriverException as err:
        raise ChromeAuthError(
            "Unable to start or control headed Chrome; check Chrome, its driver, "
            "the display, and whether the profile is already in use"
        ) from err
    finally:
        if driver is not None:
            try:
                driver.quit()
            except WebDriverException:
                # The browser is already outside the authentication flow; do
                # not mask a useful bootstrap error with teardown noise.
                pass
