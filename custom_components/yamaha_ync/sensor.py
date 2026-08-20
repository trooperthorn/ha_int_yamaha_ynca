"""Read-only descriptive state: friendly input names and current DSP mode.

Sound_Program and Enhancer_Type are exposed here rather than as `select`
entities because the full valid-option list for either isn't known -- only
today's live value ("Surround Decoder" / "High Resolution") has been
confirmed against this unit. A `select` with a guessed option list would
either reject valid choices or silently accept invalid ones; a sensor makes
no such claim.
"""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from homeassistant.components.sensor import SensorEntity, SensorEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .coordinator import YncCoordinator, ZoneState
from .entity import YncZoneEntity


@dataclass(frozen=True, kw_only=True)
class YncSensorDescription(SensorEntityDescription):
    value_fn: Callable[[ZoneState], str | None]
    supported_fn: Callable[[ZoneState], bool] = lambda zone: True


SENSOR_DESCRIPTIONS: tuple[YncSensorDescription, ...] = (
    YncSensorDescription(
        key="input_title",
        translation_key="input_title",
        value_fn=lambda zone: zone.status.input_title,
        supported_fn=lambda zone: zone.status.input_title is not None,
    ),
    YncSensorDescription(
        key="sound_program",
        translation_key="sound_program",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda zone: zone.status.sound_program,
        supported_fn=lambda zone: zone.status.sound_program is not None,
    ),
    YncSensorDescription(
        key="enhancer_type",
        translation_key="enhancer_type",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda zone: zone.status.enhancer_type,
        supported_fn=lambda zone: zone.status.enhancer_type is not None,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator: YncCoordinator = entry.runtime_data
    entities = [
        YncSensor(coordinator, zone_id, description)
        for zone_id, zone in coordinator.data.zones.items()
        for description in SENSOR_DESCRIPTIONS
        if description.supported_fn(zone)
    ]
    async_add_entities(entities)


class YncSensor(YncZoneEntity, SensorEntity):
    entity_description: YncSensorDescription

    def __init__(
        self, coordinator: YncCoordinator, zone_id: str, description: YncSensorDescription
    ) -> None:
        self.entity_description = description
        super().__init__(coordinator, zone_id, key=description.key)

    @property
    def native_value(self) -> str | None:
        return self.entity_description.value_fn(self._zone)
