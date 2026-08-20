"""Precise numeric controls: dB-scale volume/trim and dialogue tuning."""
from __future__ import annotations

from collections.abc import Callable, Coroutine
from dataclasses import dataclass
from typing import Any

from homeassistant.components.number import (
    NumberEntity,
    NumberEntityDescription,
    NumberMode,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .coordinator import YncCoordinator, ZoneState
from .entity import YncZoneEntity


@dataclass(frozen=True, kw_only=True)
class YncNumberDescription(NumberEntityDescription):
    value_fn: Callable[[ZoneState], float | int | None]
    set_fn: Callable[[YncCoordinator, str, float], Coroutine[Any, Any, None]]
    supported_fn: Callable[[ZoneState], bool] = lambda zone: True


NUMBER_DESCRIPTIONS: tuple[YncNumberDescription, ...] = (
    YncNumberDescription(
        key="volume_db",
        translation_key="volume_db",
        native_min_value=-80.5,
        native_max_value=16.5,
        native_step=0.5,
        native_unit_of_measurement="dB",
        mode=NumberMode.BOX,
        value_fn=lambda zone: zone.status.volume_db,
        set_fn=lambda coordinator, zone_id, value: coordinator.client.set_volume_db(
            zone_id, value
        ),
        supported_fn=lambda zone: zone.capabilities.has_volume,
    ),
    YncNumberDescription(
        key="subwoofer_trim_db",
        translation_key="subwoofer_trim_db",
        native_min_value=-6.0,
        native_max_value=6.0,
        native_step=0.5,
        native_unit_of_measurement="dB",
        entity_category=EntityCategory.CONFIG,
        value_fn=lambda zone: zone.status.subwoofer_trim_db,
        set_fn=lambda coordinator, zone_id, value: coordinator.client.set_subwoofer_trim_db(
            zone_id, value
        ),
        supported_fn=lambda zone: zone.status.subwoofer_trim_db is not None,
    ),
    YncNumberDescription(
        key="dialogue_lift",
        translation_key="dialogue_lift",
        native_min_value=0,
        native_max_value=5,
        native_step=1,
        entity_category=EntityCategory.CONFIG,
        value_fn=lambda zone: zone.status.dialogue_lift,
        set_fn=lambda coordinator, zone_id, value: coordinator.client.set_dialogue_lift(
            zone_id, int(value)
        ),
        supported_fn=lambda zone: zone.status.dialogue_lift is not None,
    ),
    YncNumberDescription(
        key="dialogue_level",
        translation_key="dialogue_level",
        native_min_value=0,
        native_max_value=3,
        native_step=1,
        entity_category=EntityCategory.CONFIG,
        value_fn=lambda zone: zone.status.dialogue_level,
        set_fn=lambda coordinator, zone_id, value: coordinator.client.set_dialogue_level(
            zone_id, int(value)
        ),
        supported_fn=lambda zone: zone.status.dialogue_level is not None,
    ),
    YncNumberDescription(
        key="dts_dialogue_control",
        translation_key="dts_dialogue_control",
        native_min_value=0,
        native_max_value=6,
        native_step=1,
        entity_category=EntityCategory.CONFIG,
        value_fn=lambda zone: zone.status.dts_dialogue_control,
        set_fn=lambda coordinator, zone_id, value: coordinator.client.set_dts_dialogue_control(
            zone_id, int(value)
        ),
        supported_fn=lambda zone: zone.status.dts_dialogue_control is not None,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator: YncCoordinator = entry.runtime_data
    entities = [
        YncNumber(coordinator, zone_id, description)
        for zone_id, zone in coordinator.data.zones.items()
        for description in NUMBER_DESCRIPTIONS
        if description.supported_fn(zone)
    ]
    async_add_entities(entities)


class YncNumber(YncZoneEntity, NumberEntity):
    entity_description: YncNumberDescription

    def __init__(
        self, coordinator: YncCoordinator, zone_id: str, description: YncNumberDescription
    ) -> None:
        self.entity_description = description
        super().__init__(coordinator, zone_id, key=description.key)

    @property
    def native_value(self) -> float | int | None:
        return self.entity_description.value_fn(self._zone)

    async def async_set_native_value(self, value: float) -> None:
        await self.entity_description.set_fn(self.coordinator, self._zone_id, value)
        await self.coordinator.async_request_refresh()
