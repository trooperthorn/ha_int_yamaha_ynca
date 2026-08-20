"""One remote entity per zone: scene recall as "activities", plus a
send_command dispatch for scenes/inputs/transport control.

Yamaha's own scene system (Config/Name/Scene, confirmed live -- e.g. "Movie
Viewing", "TV Viewing") is exactly what HA's RemoteEntity calls an activity:
"a predefined activity or macro that puts the remote in a specific state."
There's no "currently active scene" reported by the device (scenes are
momentary macros, not sticky state), so `current_activity` stays None --
that's an explicitly supported value per the entity's own docs, not a gap.
"""
from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from homeassistant.components.remote import RemoteEntity, RemoteEntityFeature
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .client import YncConnectionError
from .const import (
    NETUSB_FAMILY_INPUTS,
    PLAYBACK_PAUSE,
    PLAYBACK_PLAY,
    PLAYBACK_SKIP_FWD,
    PLAYBACK_SKIP_REV,
    PLAYBACK_STOP,
)
from .coordinator import YncCoordinator
from .entity import YncZoneEntity
from .xml_protocol import YncProtocolError

PARALLEL_UPDATES = 0

_TRANSPORT_COMMANDS = {
    "play": PLAYBACK_PLAY,
    "pause": PLAYBACK_PAUSE,
    "stop": PLAYBACK_STOP,
    "next": PLAYBACK_SKIP_FWD,
    "previous": PLAYBACK_SKIP_REV,
}


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator: YncCoordinator = entry.runtime_data
    async_add_entities(
        YncRemote(coordinator, zone_id) for zone_id in coordinator.data.zones
    )


class YncRemote(YncZoneEntity, RemoteEntity):
    _attr_name = None

    def __init__(self, coordinator: YncCoordinator, zone_id: str) -> None:
        super().__init__(coordinator, zone_id, key="remote")
        scenes = self._zone.capabilities.scene_names
        self._scene_number_by_name = {
            name: int(key.rsplit("_", 1)[-1]) for key, name in scenes.items()
        }
        self._attr_supported_features = (
            RemoteEntityFeature.ACTIVITY if scenes else RemoteEntityFeature(0)
        )
        self._attr_activity_list = list(self._scene_number_by_name) or None

    @property
    def is_on(self) -> bool | None:
        return self._zone.status.power

    async def async_turn_on(self, activity: str | None = None, **kwargs: Any) -> None:
        if activity is not None:
            await self._async_recall_scene(activity)
        else:
            await self.coordinator.client.set_power(self._zone_id, True)
            await self.coordinator.async_request_refresh()

    async def async_turn_off(self, activity: str | None = None, **kwargs: Any) -> None:
        await self.coordinator.client.set_power(self._zone_id, False)
        await self.coordinator.async_request_refresh()

    async def async_send_command(self, command: Iterable[str], **kwargs: Any) -> None:
        num_repeats = kwargs.get("num_repeats", 1)
        for _ in range(num_repeats):
            for single_command in command:
                await self._async_dispatch_command(single_command)
        await self.coordinator.async_request_refresh()

    async def _async_dispatch_command(self, command: str) -> None:
        if command in self._scene_number_by_name:
            await self._async_recall_scene(command)
            return

        device = self.coordinator.data.device
        input_id = next(
            (k for k, v in device.input_names.items() if v == command), None
        )
        if input_id is not None:
            await self.coordinator.client.set_input(self._zone_id, input_id)
            return

        transport = _TRANSPORT_COMMANDS.get(command.lower())
        if transport is not None:
            input_id = self._zone.status.input_id
            if input_id not in NETUSB_FAMILY_INPUTS:
                raise HomeAssistantError(
                    f"Zone is not on a playable source, can't send {command!r}"
                )
            try:
                await self.coordinator.client.netusb_playback(input_id, transport)
            except (YncProtocolError, YncConnectionError) as err:
                raise HomeAssistantError(f"Command {command!r} failed: {err}") from err
            return

        raise HomeAssistantError(
            f"Unknown command {command!r} -- expected a scene name "
            f"({', '.join(self._scene_number_by_name) or 'none configured'}), "
            f"an input name, or one of {', '.join(_TRANSPORT_COMMANDS)}"
        )

    async def _async_recall_scene(self, name: str) -> None:
        scene_number = self._scene_number_by_name.get(name)
        if scene_number is None:
            raise HomeAssistantError(
                f"Unknown scene {name!r} -- expected one of "
                f"{', '.join(self._scene_number_by_name) or 'none configured'}"
            )
        await self.coordinator.client.recall_scene(self._zone_id, scene_number)
        await self.coordinator.async_request_refresh()
