"""Toggleable zone behaviors: party-mode linking, pure direct, HDMI outputs."""
from __future__ import annotations

from collections.abc import Callable, Coroutine
from dataclasses import dataclass
from typing import Any

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .coordinator import YncCoordinator, ZoneState
from .entity import YncZoneEntity


@dataclass(frozen=True, kw_only=True)
class YncSwitchDescription(SwitchEntityDescription):
    is_on_fn: Callable[[ZoneState], bool | None]
    set_fn: Callable[[YncCoordinator, str, bool], Coroutine[Any, Any, None]]
    supported_fn: Callable[[ZoneState], bool] = lambda zone: True


SWITCH_DESCRIPTIONS: tuple[YncSwitchDescription, ...] = (
    YncSwitchDescription(
        key="party_mode",
        translation_key="party_mode",
        is_on_fn=lambda zone: zone.status.party_mode,
        set_fn=lambda coordinator, zone_id, on: coordinator.client.set_party_mode(
            zone_id, on
        ),
        supported_fn=lambda zone: zone.status.party_mode is not None,
    ),
    YncSwitchDescription(
        key="pure_direct",
        translation_key="pure_direct",
        entity_category=EntityCategory.CONFIG,
        is_on_fn=lambda zone: zone.status.pure_direct,
        set_fn=lambda coordinator, zone_id, on: coordinator.client.set_pure_direct(
            zone_id, on
        ),
        supported_fn=lambda zone: zone.status.pure_direct is not None,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator: YncCoordinator = entry.runtime_data
    entities: list[SwitchEntity] = [
        YncSwitch(coordinator, zone_id, description)
        for zone_id, zone in coordinator.data.zones.items()
        for description in SWITCH_DESCRIPTIONS
        if description.supported_fn(zone)
    ]
    entities.extend(
        YncHdmiOutputSwitch(coordinator, zone_id, output_id)
        for zone_id, zone in coordinator.data.zones.items()
        for output_id in zone.status.hdmi_outputs
    )
    async_add_entities(entities)


class YncSwitch(YncZoneEntity, SwitchEntity):
    entity_description: YncSwitchDescription

    def __init__(
        self, coordinator: YncCoordinator, zone_id: str, description: YncSwitchDescription
    ) -> None:
        self.entity_description = description
        super().__init__(coordinator, zone_id, key=description.key)

    @property
    def is_on(self) -> bool | None:
        return self.entity_description.is_on_fn(self._zone)

    async def async_turn_on(self, **kwargs: Any) -> None:
        await self.entity_description.set_fn(self.coordinator, self._zone_id, True)
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self.entity_description.set_fn(self.coordinator, self._zone_id, False)
        await self.coordinator.async_request_refresh()


class YncHdmiOutputSwitch(YncZoneEntity, SwitchEntity):
    """One switch per physical HDMI output the zone reports (e.g. OUT_1, OUT_2)."""

    entity_category = EntityCategory.CONFIG

    def __init__(self, coordinator: YncCoordinator, zone_id: str, output_id: str) -> None:
        self._output_id = output_id
        super().__init__(coordinator, zone_id, key=f"hdmi_{output_id.lower()}")
        self._attr_translation_key = "hdmi_output"
        self._attr_translation_placeholders = {
            "output": output_id.replace("OUT_", "")
        }

    @property
    def is_on(self) -> bool | None:
        return self._zone.status.hdmi_outputs.get(self._output_id)

    async def async_turn_on(self, **kwargs: Any) -> None:
        await self.coordinator.client.set_hdmi_output(self._zone_id, self._output_id, True)
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self.coordinator.client.set_hdmi_output(self._zone_id, self._output_id, False)
        await self.coordinator.async_request_refresh()
