"""SmartThings Find NextGen integration setup."""

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .const import CONF_JSESSION_ID, CONF_REGION, DOMAIN, REGION_EUROPE
from .coordinator import SmartTagCoordinator

PLATFORMS = [Platform.DEVICE_TRACKER, Platform.BUTTON]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up SmartThings Find NextGen from a config entry."""
    hass.data.setdefault(DOMAIN, {})

    coordinator = SmartTagCoordinator(
        hass,
        entry.data[CONF_JSESSION_ID].strip(),
        entry.data.get(CONF_REGION, REGION_EUROPE),
    )
    await coordinator.async_config_entry_first_refresh()

    hass.data[DOMAIN][entry.entry_id] = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    entry.async_on_unload(entry.add_update_listener(async_reload_entry))
    return True


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload the integration after config-entry data changes."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id, None)
    return unload_ok
