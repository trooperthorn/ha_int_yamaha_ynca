"""Passive, non-settable zone facts."""
from __future__ import annotations

from homeassistant.components.binary_sensor import (
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .coordinator import YncCoordinator
from .entity import YncZoneEntity

NO_LOCAL_AMP_DESCRIPTION = BinarySensorEntityDescription(
    key="no_local_amplifier",
    translation_key="no_local_amplifier",
    entity_category=EntityCategory.DIAGNOSTIC,
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator: YncCoordinator = entry.runtime_data
    async_add_entities(
        YncNoLocalAmplifierSensor(coordinator, zone_id)
        for zone_id in coordinator.data.zones
    )


class YncNoLocalAmplifierSensor(YncZoneEntity, BinarySensorEntity):
    """True when Volume_Existence: Not Exist -- this zone needs an external amp.

    Computed once from Zone_N/Config at setup rather than polled, since the
    receiver doesn't grow or lose amplifier hardware at runtime. Exists so
    routing automations (e.g. handing a line-out-only zone off to an
    external amplifier) can key off zone capability instead of a hardcoded
    zone id.
    """

    entity_description = NO_LOCAL_AMP_DESCRIPTION

    def __init__(self, coordinator: YncCoordinator, zone_id: str) -> None:
        super().__init__(coordinator, zone_id, key=NO_LOCAL_AMP_DESCRIPTION.key)

    @property
    def is_on(self) -> bool:
        return not self._zone.capabilities.has_volume
