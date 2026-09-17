#!/usr/bin/env python3
"""Open a headed Chrome session and print the SmartThings Find JSESSIONID.

This is an interactive bootstrap helper. It does not bypass CAPTCHA, MFA, or
Samsung security checks; complete those steps normally in the browser window.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from selenium import webdriver
from selenium.webdriver.chrome.options import Options

URL = "https://smartthingsfind.samsung.com/"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--profile-dir",
        type=Path,
        default=Path.home() / ".smartthings-find-ha" / "chrome-profile",
        help="Persistent Chrome profile directory",
    )
    args = parser.parse_args()

    args.profile_dir.mkdir(parents=True, exist_ok=True)
    options = Options()
    options.add_argument(f"--user-data-dir={args.profile_dir}")
    options.add_argument("--start-maximized")

    driver = webdriver.Chrome(options=options)
    try:
        driver.get(URL)
        input("Complete Samsung sign-in in Chrome, then press Enter here... ")
        cookie = driver.get_cookie("JSESSIONID")
        if not cookie or not cookie.get("value"):
            raise SystemExit("JSESSIONID was not found in the SmartThings Find session")
        print("JSESSIONID (keep it private):")
        print(cookie["value"])
    finally:
        driver.quit()


if __name__ == "__main__":
    main()
