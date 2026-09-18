"""Diagnostic sensors for SmartThings Find HA."""

from __future__ import annotations

from typing import Any

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import SmartTagCoordinator


BATTERY_ICONS = {
    "HIGH": "mdi:battery-high",
    "MEDIUM": "mdi:battery-medium",
    "LOW": "mdi:battery-low",
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up battery-state sensors for discovered SmartTags."""
    coordinator: SmartTagCoordinator = hass.data[DOMAIN][entry.entry_id]
    known_device_ids: set[str] = set()

    @callback
    def async_add_new_entities() -> None:
        data = coordinator.data or {}
        new_device_ids = set(data) - known_device_ids
        if not new_device_ids:
            return

        async_add_entities(
            [
                SmartTagBatteryStateSensor(coordinator, device_id)
                for device_id in new_device_ids
            ]
        )
        known_device_ids.update(new_device_ids)

    async_add_new_entities()
    entry.async_on_unload(coordinator.async_add_listener(async_add_new_entities))


class SmartTagBatteryStateSensor(
    CoordinatorEntity[SmartTagCoordinator], SensorEntity
):
    """Expose Samsung's raw SmartTag battery state."""

    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_has_entity_name = True
    _attr_name = "Battery state"
    _attr_icon = "mdi:battery-unknown"

    def __init__(self, coordinator: SmartTagCoordinator, device_id: str) -> None:
        super().__init__(coordinator)
        self.device_id = device_id
        self._attr_unique_id = f"smarttag_battery_state_{device_id}"

    @property
    def tag_data(self) -> dict[str, Any]:
        """Return the latest data block for this SmartTag."""
        return (self.coordinator.data or {}).get(self.device_id, {})

    @property
    def native_value(self) -> str | None:
        """Return Samsung's raw battery state without inventing precision."""
        battery_state = self.tag_data.get("battery")
        if battery_state is None:
            return None
        return str(battery_state).upper()

    @property
    def icon(self) -> str:
        """Use a battery icon matching the raw state."""
        return BATTERY_ICONS.get(self.native_value, "mdi:battery-unknown")

    @property
    def device_info(self) -> DeviceInfo:
        """Attach the sensor to the existing SmartTag device."""
        return DeviceInfo(
            identifiers={(DOMAIN, self.device_id)},
            name=self.tag_data.get("name", "SmartTag"),
            manufacturer="Samsung",
            model=self.tag_data.get("model") or "SmartTag",
        )
