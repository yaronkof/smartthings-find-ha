"""Manual actions for SmartThings Find NextGen."""

from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import SmartTagCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Create one safe, per-device location refresh button per SmartTag."""
    coordinator: SmartTagCoordinator = hass.data[DOMAIN][entry.entry_id]
    known_device_ids: set[str] = set()

    def add_buttons() -> None:
        data = coordinator.data or {}
        new_ids = set(data) - known_device_ids
        if new_ids:
            async_add_entities(
                [SmartTagLocateButton(coordinator, device_id) for device_id in new_ids]
            )
            known_device_ids.update(new_ids)

    add_buttons()
    entry.async_on_unload(coordinator.async_add_listener(add_buttons))


class SmartTagLocateButton(
    CoordinatorEntity[SmartTagCoordinator], ButtonEntity
):
    """Request a fresh location using Samsung's existing set-last-select API."""

    _attr_icon = "mdi:map-marker-refresh"
    _attr_translation_key = "locate"

    def __init__(self, coordinator: SmartTagCoordinator, device_id: str) -> None:
        super().__init__(coordinator)
        self.device_id = device_id
        self._attr_unique_id = f"smarttag_{device_id}_locate"

    @property
    def name(self) -> str:
        """Return the action name for this SmartTag."""
        tag_data = (self.coordinator.data or {}).get(self.device_id, {})
        return f"{tag_data.get('name', 'SmartTag')} Locate"

    @property
    def device_info(self) -> DeviceInfo:
        """Attach the action to the same physical SmartTag as the tracker."""
        tag_data = (self.coordinator.data or {}).get(self.device_id, {})
        return DeviceInfo(
            identifiers={(DOMAIN, self.device_id)},
            name=tag_data.get("name", "SmartTag"),
            manufacturer="Samsung",
            model=tag_data.get("model") or "SmartTag",
        )

    async def async_press(self) -> None:
        """Request a fresh location and publish the returned operation data."""
        await self.coordinator.async_refresh_device(self.device_id)
