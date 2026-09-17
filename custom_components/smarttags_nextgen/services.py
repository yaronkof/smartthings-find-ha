"""Services exposed by SmartThings Find NextGen."""

from __future__ import annotations

from collections.abc import Iterable

import voluptuous as vol
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import ConfigEntryAuthFailed, HomeAssistantError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import entity_registry as er

from .const import CONF_DEVICE_ID, DOMAIN, SERVICE_LOCATE, SERVICE_REFRESH
from .coordinator import SmartTagCoordinator

LOCATE_SCHEMA = vol.Schema(
    {
        vol.Optional(ATTR_ENTITY_ID): cv.entity_ids,
        vol.Optional(CONF_DEVICE_ID): cv.string,
    }
)
REFRESH_SCHEMA = vol.Schema({})


def _coordinators(hass: HomeAssistant) -> Iterable[tuple[str, SmartTagCoordinator]]:
    """Yield loaded entry coordinators without exposing credentials."""
    for entry_id, candidate in hass.data.get(DOMAIN, {}).items():
        if isinstance(candidate, SmartTagCoordinator):
            yield entry_id, candidate


def _device_id_from_unique_id(unique_id: str) -> str | None:
    """Extract a device id from one of this integration's entity unique ids."""
    prefix = "smarttag_"
    if not unique_id.startswith(prefix):
        return None
    value = unique_id[len(prefix) :]
    if value.endswith("_locate"):
        value = value[: -len("_locate")]
    return value or None


def _target_device_ids(hass: HomeAssistant, call: ServiceCall) -> set[str]:
    """Resolve service targets through the entity registry, not user-facing names."""
    device_ids = {call.data[CONF_DEVICE_ID]} if call.data.get(CONF_DEVICE_ID) else set()
    registry = er.async_get(hass)
    for entity_id in call.data.get(ATTR_ENTITY_ID, []):
        entity = registry.async_get(entity_id)
        if entity is None or entity.domain not in {"device_tracker", "button"}:
            continue
        device_id = _device_id_from_unique_id(entity.unique_id)
        if device_id:
            device_ids.add(device_id)
    return device_ids


async def async_locate(hass: HomeAssistant, call: ServiceCall) -> None:
    """Request a fresh location for one or more SmartTags."""
    requested = _target_device_ids(hass, call)
    if not requested:
        raise HomeAssistantError("Provide a SmartTag entity_id or device_id")

    found: set[str] = set()
    for _entry_id, coordinator in _coordinators(hass):
        for device_id in requested & set(coordinator.data or {}):
            found.add(device_id)
            try:
                await coordinator.async_refresh_device(device_id)
            except ConfigEntryAuthFailed:
                # The coordinator has already translated the server response into
                # HA's reauth mechanism; do not log or repeat the credential.
                raise

    if found != requested:
        missing = len(requested - found)
        raise HomeAssistantError(f"{missing} SmartTag target(s) are not loaded")


async def async_refresh(hass: HomeAssistant, _call: ServiceCall) -> None:
    """Refresh all loaded SmartThings Find config entries."""
    for _entry_id, coordinator in _coordinators(hass):
        await coordinator.async_request_refresh()


async def async_setup(hass: HomeAssistant) -> bool:
    """Register integration-level services once per Home Assistant instance."""
    hass.services.async_register(
        DOMAIN, SERVICE_LOCATE, lambda call: async_locate(hass, call), LOCATE_SCHEMA
    )
    hass.services.async_register(
        DOMAIN, SERVICE_REFRESH, lambda call: async_refresh(hass, call), REFRESH_SCHEMA
    )
    return True
