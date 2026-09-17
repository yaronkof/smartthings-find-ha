"""Strictly redacted diagnostics for SmartThings Find NextGen."""

from __future__ import annotations

from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import CONF_JSESSION_ID, CONF_REGION, DOMAIN


def _exception_type(value: Any) -> str | None:
    """Return only an exception class name; never serialize its message."""
    return type(value).__name__ if value is not None else None


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    """Return useful operational counters while excluding all account data."""
    coordinator = hass.data.get(DOMAIN, {}).get(entry.entry_id)
    data = coordinator.data if coordinator is not None else None
    api = getattr(coordinator, "api", None)
    return {
        "config": {
            "region": entry.data.get(CONF_REGION),
            "has_jsession_id": bool(entry.data.get(CONF_JSESSION_ID)),
        },
        "coordinator": {
            "loaded": coordinator is not None,
            "device_count": len(data) if isinstance(data, dict) else 0,
            "last_update_success": getattr(coordinator, "last_update_success", None),
            "last_exception_type": _exception_type(
                getattr(coordinator, "last_exception", None)
            ),
            "update_interval_seconds": getattr(
                getattr(coordinator, "update_interval", None), "total_seconds", lambda: None
            )(),
        },
        "api": {"csrf_initialized": bool(getattr(api, "csrf_token", None))},
    }
