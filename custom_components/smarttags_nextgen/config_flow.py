"""Config flow for SmartThings Find NextGen."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import (
    SmartTagsAPI,
    SmartTagsAuthenticationError,
    SmartTagsConnectionError,
)
from .chrome_auth import ChromeAuthError, get_jsession_id_from_chrome
from .const import (
    AUTH_CHROME,
    AUTH_MANUAL,
    CONF_AUTH_METHOD,
    CONF_JSESSION_ID,
    CONF_REGION,
    DOMAIN,
    REGION_ASIA,
    REGION_ASIA_2,
    REGION_EUROPE,
    REGION_US_GENERAL,
)

_LOGGER = logging.getLogger(__name__)

AUTH_OPTIONS = {
    AUTH_MANUAL: "Manual JSESSIONID",
    AUTH_CHROME: "Headed Chrome persistent profile",
}

REGION_OPTIONS = {
    REGION_EUROPE: "Europe (prd-eu)",
    REGION_US_GENERAL: "General / US (prd-us)",
    REGION_ASIA: "Asia / Pacific (prd-ap)",
    REGION_ASIA_2: "Asia / Pacific 2 (prd-ap2)",
    "custom": "Other / Custom...",
}
KNOWN_REGIONS = {
    REGION_EUROPE,
    REGION_US_GENERAL,
    REGION_ASIA,
    REGION_ASIA_2,
}


class CannotConnect(HomeAssistantError):
    """Raised when SmartThings Find cannot be reached."""


class InvalidAuth(HomeAssistantError):
    """Raised when the Samsung browser session is invalid."""


class ChromeBootstrapFailed(HomeAssistantError):
    """Raised when the optional manual Chrome bootstrap cannot complete."""


async def validate_input(hass: HomeAssistant, data: dict[str, Any]) -> dict[str, Any]:
    """Validate a JSESSIONID and region against SmartThings Find."""
    api = SmartTagsAPI(
        async_get_clientsession(hass),
        data[CONF_JSESSION_ID],
        data[CONF_REGION],
    )
    try:
        await api.refresh_csrf_token()
        await api.get_devices()
    except SmartTagsAuthenticationError as err:
        raise InvalidAuth from err
    except SmartTagsConnectionError as err:
        raise CannotConnect from err

    return {"title": "SmartThings Find Account"}


def _normalize_input(user_input: dict[str, Any]) -> tuple[dict[str, Any] | None, dict[str, str]]:
    """Convert UI region selection to the value stored in the config entry."""
    errors: dict[str, str] = {}
    region_selection = user_input.get(CONF_REGION, REGION_EUROPE)
    actual_region = region_selection

    if region_selection == "custom":
        custom_region = str(user_input.get("custom_region", "")).strip()
        if not custom_region:
            errors["custom_region"] = "empty_custom_region"
        else:
            actual_region = custom_region

    jsession_id = str(user_input.get(CONF_JSESSION_ID, "")).strip()
    if not jsession_id:
        errors[CONF_JSESSION_ID] = "empty_jsession_id"

    if errors:
        return None, errors

    return {
        CONF_JSESSION_ID: jsession_id,
        CONF_REGION: actual_region,
    }, errors


async def _normalize_with_auth(
    hass: HomeAssistant, user_input: dict[str, Any]
) -> tuple[dict[str, Any] | None, dict[str, str]]:
    """Resolve either the pasted cookie or one explicit headed Chrome session."""
    if user_input.get(CONF_AUTH_METHOD, AUTH_MANUAL) == AUTH_CHROME:
        try:
            jsession_id = await hass.async_add_executor_job(
                get_jsession_id_from_chrome,
                hass.config.path("smarttags_nextgen", "chrome-profile"),
            )
        except ChromeAuthError as err:
            raise ChromeBootstrapFailed from err
        user_input = {**user_input, CONF_JSESSION_ID: jsession_id}
    return _normalize_input(user_input)


def _description_placeholders(hass: HomeAssistant) -> dict[str, str]:
    """Provide the stable profile location without exposing cookie contents."""
    return {
        "url": "https://smartthingsfind.samsung.com",
        "profile": hass.config.path("smarttags_nextgen", "chrome-profile"),
    }


def _schema(
    *,
    auth_method: str = AUTH_MANUAL,
    jsession_id: str = "",
    region: str = REGION_EUROPE,
    custom_region: str = "",
) -> vol.Schema:
    """Build the shared setup/reconfigure form schema."""
    return vol.Schema(
        {
            vol.Required(CONF_AUTH_METHOD, default=auth_method): vol.In(AUTH_OPTIONS),
            vol.Optional(CONF_JSESSION_ID, default=jsession_id): str,
            vol.Required(CONF_REGION, default=region): vol.In(REGION_OPTIONS),
            vol.Optional("custom_region", default=custom_region): str,
        }
    )


def _region_defaults(stored_region: str) -> tuple[str, str]:
    """Translate a stored custom region back to form defaults."""
    if stored_region in KNOWN_REGIONS:
        return stored_region, ""
    return "custom", stored_region


class SmartTagsConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle the SmartThings Find NextGen config flow."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Handle initial setup."""
        errors: dict[str, str] = {}

        if user_input is not None:
            try:
                validation_data, errors = await _normalize_with_auth(
                    self.hass, user_input
                )
            except ChromeBootstrapFailed:
                validation_data, errors = None, {"base": "chrome_auth_failed"}
            if validation_data is not None:
                try:
                    info = await validate_input(self.hass, validation_data)
                except InvalidAuth:
                    errors["base"] = "invalid_auth"
                except CannotConnect:
                    errors["base"] = "cannot_connect"
                except Exception:  # noqa: BLE001
                    _LOGGER.exception("Unexpected error validating SmartThings Find")
                    errors["base"] = "unknown"
                else:
                    return self.async_create_entry(
                        title=info["title"], data=validation_data
                    )

        return self.async_show_form(
            step_id="user",
            data_schema=_schema(
                auth_method=(user_input or {}).get(CONF_AUTH_METHOD, AUTH_MANUAL),
                jsession_id=(user_input or {}).get(CONF_JSESSION_ID, ""),
                region=(user_input or {}).get(CONF_REGION, REGION_EUROPE),
                custom_region=(user_input or {}).get("custom_region", ""),
            ),
            errors=errors,
            description_placeholders=_description_placeholders(self.hass),
        )

    async def async_step_reauth(
        self, entry_data: dict[str, Any]
    ) -> config_entries.ConfigFlowResult:
        """Start reauthentication when the Samsung session expires."""
        self._reauth_entry = self.hass.config_entries.async_get_entry(
            self.context["entry_id"]
        )
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Validate and store a replacement JSESSIONID."""
        entry = self._reauth_entry
        if entry is None:
            return self.async_abort(reason="reauth_failed")

        errors: dict[str, str] = {}
        current_region = entry.data.get(CONF_REGION, REGION_EUROPE)

        if user_input is not None:
            try:
                validation_data, _ = await _normalize_with_auth(
                    self.hass, {**user_input, CONF_REGION: current_region}
                )
            except ChromeBootstrapFailed:
                validation_data = None
                errors["base"] = "chrome_auth_failed"
            validation_data = validation_data or {
                CONF_JSESSION_ID: "",
                CONF_REGION: current_region,
            }
            if not validation_data[CONF_JSESSION_ID]:
                errors[CONF_JSESSION_ID] = "empty_jsession_id"
                return self.async_show_form(
                    step_id="reauth_confirm",
                    data_schema=vol.Schema(
                        {
                            vol.Required(CONF_AUTH_METHOD, default=AUTH_MANUAL): vol.In(
                                AUTH_OPTIONS
                            ),
                            vol.Optional(CONF_JSESSION_ID): str,
                        }
                    ),
                    errors=errors,
                    description_placeholders=_description_placeholders(self.hass),
                )
            try:
                await validate_input(self.hass, validation_data)
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except Exception:  # noqa: BLE001
                _LOGGER.exception("Unexpected error during SmartThings Find reauth")
                errors["base"] = "unknown"
            else:
                self.hass.config_entries.async_update_entry(
                    entry,
                    data={**entry.data, CONF_JSESSION_ID: validation_data[CONF_JSESSION_ID]},
                )
                await self.hass.config_entries.async_reload(entry.entry_id)
                return self.async_abort(reason="reauth_successful")

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_AUTH_METHOD, default=AUTH_MANUAL): vol.In(
                        AUTH_OPTIONS
                    ),
                    vol.Optional(CONF_JSESSION_ID): str,
                }
            ),
            errors=errors,
            description_placeholders=_description_placeholders(self.hass),
        )

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> config_entries.OptionsFlow:
        """Return the options flow for manual credential/region updates."""
        return SmartTagsOptionsFlowHandler()


class SmartTagsOptionsFlowHandler(config_entries.OptionsFlow):
    """Allow manual JSESSIONID, headed Chrome, and region updates."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Edit connection settings."""
        errors: dict[str, str] = {}

        if user_input is not None:
            try:
                validation_data, errors = await _normalize_with_auth(
                    self.hass, user_input
                )
            except ChromeBootstrapFailed:
                validation_data, errors = None, {"base": "chrome_auth_failed"}
            if validation_data is not None:
                try:
                    await validate_input(self.hass, validation_data)
                except InvalidAuth:
                    errors["base"] = "invalid_auth"
                except CannotConnect:
                    errors["base"] = "cannot_connect"
                except Exception:  # noqa: BLE001
                    _LOGGER.exception("Unexpected error updating SmartThings Find")
                    errors["base"] = "unknown"
                else:
                    self.hass.config_entries.async_update_entry(
                        self.config_entry, data=validation_data
                    )
                    return self.async_create_entry(title="", data={})

        if user_input is not None:
            jsession_default = user_input.get(CONF_JSESSION_ID, "")
            region_default = user_input.get(CONF_REGION, REGION_EUROPE)
            custom_region_default = user_input.get("custom_region", "")
        else:
            jsession_default = self.config_entry.data.get(CONF_JSESSION_ID, "")
            region_default, custom_region_default = _region_defaults(
                self.config_entry.data.get(CONF_REGION, REGION_EUROPE)
            )

        return self.async_show_form(
            step_id="init",
            data_schema=_schema(
                auth_method=(user_input or {}).get(CONF_AUTH_METHOD, AUTH_MANUAL),
                jsession_id=jsession_default,
                region=region_default,
                custom_region=custom_region_default,
            ),
            errors=errors,
            description_placeholders=_description_placeholders(self.hass),
        )
