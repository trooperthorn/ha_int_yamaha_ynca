"""Auto/On/Off style tri-state DSP toggles.

The Auto/On/Off option set is standard across Yamaha's YPAO/Extra Bass/
Adaptive DRC controls and matched what this unit reported live, but hasn't
been cross-checked against the full per-model option list -- an invalid
PUT comes back as a nonzero RC, which `client.py` already turns into a
`YncProtocolError` the platform surfaces as a proper HA exception rather
than silently doing nothing.
"""
from __future__ import annotations

from collections.abc import Callable, Coroutine
from dataclasses import dataclass
from typing import Any

from homeassistant.components.select import SelectEntity, SelectEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .client import YncConnectionError
from .coordinator import YncCoordinator, ZoneState
from .entity import YncZoneEntity
from .xml_protocol import YncProtocolError

# client.py serializes every request through its own asyncio.Lock already.
PARALLEL_UPDATES = 0

AUTO_ON_OFF = ("Auto", "On", "Off")


@dataclass(frozen=True, kw_only=True)
class YncSelectDescription(SelectEntityDescription):
    value_fn: Callable[[ZoneState], str | None]
    set_fn: Callable[[YncCoordinator, str, str], Coroutine[Any, Any, None]]
    supported_fn: Callable[[ZoneState], bool] = lambda zone: True


SELECT_DESCRIPTIONS: tuple[YncSelectDescription, ...] = (
    YncSelectDescription(
        key="ypao_volume",
        translation_key="ypao_volume",
        options=list(AUTO_ON_OFF),
        entity_category=EntityCategory.CONFIG,
        value_fn=lambda zone: zone.status.ypao_volume,
        set_fn=lambda coordinator, zone_id, value: coordinator.client.set_ypao_volume(
            zone_id, value
        ),
        supported_fn=lambda zone: zone.status.ypao_volume is not None,
    ),
    YncSelectDescription(
        key="extra_bass",
        translation_key="extra_bass",
        options=list(AUTO_ON_OFF),
        entity_category=EntityCategory.CONFIG,
        value_fn=lambda zone: zone.status.extra_bass,
        set_fn=lambda coordinator, zone_id, value: coordinator.client.set_extra_bass(
            zone_id, value
        ),
        supported_fn=lambda zone: zone.status.extra_bass is not None,
    ),
    YncSelectDescription(
        key="adaptive_drc",
        translation_key="adaptive_drc",
        options=list(AUTO_ON_OFF),
        entity_category=EntityCategory.CONFIG,
        value_fn=lambda zone: zone.status.adaptive_drc,
        set_fn=lambda coordinator, zone_id, value: coordinator.client.set_adaptive_drc(
            zone_id, value
        ),
        supported_fn=lambda zone: zone.status.adaptive_drc is not None,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator: YncCoordinator = entry.runtime_data
    entities = [
        YncSelect(coordinator, zone_id, description)
        for zone_id, zone in coordinator.data.zones.items()
        for description in SELECT_DESCRIPTIONS
        if description.supported_fn(zone)
    ]
    async_add_entities(entities)


class YncSelect(YncZoneEntity, SelectEntity):
    entity_description: YncSelectDescription

    def __init__(
        self, coordinator: YncCoordinator, zone_id: str, description: YncSelectDescription
    ) -> None:
        self.entity_description = description
        super().__init__(coordinator, zone_id, key=description.key)

    @property
    def current_option(self) -> str | None:
        return self.entity_description.value_fn(self._zone)

    async def async_select_option(self, option: str) -> None:
        try:
            await self.entity_description.set_fn(self.coordinator, self._zone_id, option)
        except (YncProtocolError, YncConnectionError) as err:
            raise HomeAssistantError(
                f"Receiver rejected {self.entity_description.key}={option}: {err}"
            ) from err
        await self.coordinator.async_request_refresh()
