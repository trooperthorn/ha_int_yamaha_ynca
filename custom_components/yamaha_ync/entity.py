"""Shared entity base: one HA device per receiver zone."""
from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceInfo as HaDeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, MANUFACTURER, ZONE_DISPLAY_NAMES
from .coordinator import YncCoordinator, ZoneState


class YncZoneEntity(CoordinatorEntity[YncCoordinator]):
    """Base for every entity that represents one zone's state.

    Each zone is modeled as its own HA device (Main Zone, Zone 2, Zone 3,
    Zone 4) rather than bundling everything under one device for the whole
    receiver -- matching how a multi-zone AVR is actually used (a zone can
    be powered, renamed, and automated independently of the others) and
    satisfying the Gold `devices`/`dynamic-devices` quality-scale rules,
    since zones only appear here if `Feature_Existence` confirmed them.
    """

    _attr_has_entity_name = True

    def __init__(self, coordinator: YncCoordinator, zone_id: str, key: str) -> None:
        super().__init__(coordinator)
        self._zone_id = zone_id
        self._attr_unique_id = f"{coordinator.data.device.system_id}_{zone_id}_{key}"
        self._attr_device_info = self._build_device_info()

    def _build_device_info(self) -> HaDeviceInfo:
        device = self.coordinator.data.device
        zone = self.coordinator.data.zones[self._zone_id]
        room = zone.capabilities.room_name
        zone_label = room or ZONE_DISPLAY_NAMES[self._zone_id]
        info = HaDeviceInfo(
            identifiers={(DOMAIN, f"{device.system_id}_{self._zone_id}")},
            name=f"{device.model_name} {zone_label}",
            manufacturer=MANUFACTURER,
            model=device.model_name,
            sw_version=device.version,
        )
        if self._zone_id != "main":
            info["via_device"] = (DOMAIN, f"{device.system_id}_main")
        return info

    @property
    def _zone(self) -> ZoneState:
        return self.coordinator.data.zones[self._zone_id]

    @property
    def available(self) -> bool:
        return super().available and self._zone_id in self.coordinator.data.zones
