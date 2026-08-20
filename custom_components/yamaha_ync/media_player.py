"""One media_player entity per configured zone."""
from __future__ import annotations

from homeassistant.components.media_player import (
    MediaPlayerDeviceClass,
    MediaPlayerEntity,
    MediaPlayerEntityFeature,
    MediaPlayerState,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .coordinator import YncCoordinator
from .entity import YncZoneEntity

# client.py already serializes every request through its own asyncio.Lock,
# so there's no need for HA to additionally throttle concurrent entity
# updates/service calls at the platform level.
PARALLEL_UPDATES = 0

# Typical dB span for this receiver family (confirmed by prior art in the
# `rxv` library, not yet re-confirmed against this exact unit's Max Volume
# setting) -- used only to present a 0-1 slider alongside the precise dB
# `number` entity, never as the value written back to the device.
VOLUME_DB_MIN = -80.5
VOLUME_DB_MAX = 16.5
VOLUME_DB_SPAN = VOLUME_DB_MAX - VOLUME_DB_MIN


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator: YncCoordinator = entry.runtime_data
    async_add_entities(
        YncMediaPlayer(coordinator, zone_id) for zone_id in coordinator.data.zones
    )


class YncMediaPlayer(YncZoneEntity, MediaPlayerEntity):
    _attr_name = None  # this entity *is* the zone device's primary feature
    _attr_device_class = MediaPlayerDeviceClass.RECEIVER

    def __init__(self, coordinator: YncCoordinator, zone_id: str) -> None:
        super().__init__(coordinator, zone_id, key="media_player")
        features = (
            MediaPlayerEntityFeature.TURN_ON | MediaPlayerEntityFeature.TURN_OFF
        )
        if self._zone.capabilities.has_volume:
            features |= (
                MediaPlayerEntityFeature.VOLUME_SET
                | MediaPlayerEntityFeature.VOLUME_MUTE
            )
        if self.coordinator.data.device.input_names:
            features |= MediaPlayerEntityFeature.SELECT_SOURCE
        self._attr_supported_features = features
        self._attr_source_list = sorted(self.coordinator.data.device.input_names.values())

    @property
    def state(self) -> MediaPlayerState | None:
        power = self._zone.status.power
        if power is None:
            return None
        return MediaPlayerState.ON if power else MediaPlayerState.OFF

    @property
    def volume_level(self) -> float | None:
        db = self._zone.status.volume_db
        if db is None:
            return None
        return max(0.0, min(1.0, (db - VOLUME_DB_MIN) / VOLUME_DB_SPAN))

    @property
    def is_volume_muted(self) -> bool | None:
        return self._zone.status.mute

    @property
    def source(self) -> str | None:
        return self._zone.status.input_title or self._zone.status.input_id

    async def async_turn_on(self) -> None:
        await self.coordinator.client.set_power(self._zone_id, True)
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self) -> None:
        await self.coordinator.client.set_power(self._zone_id, False)
        await self.coordinator.async_request_refresh()

    async def async_mute_volume(self, mute: bool) -> None:
        await self.coordinator.client.set_mute(self._zone_id, mute)
        await self.coordinator.async_request_refresh()

    async def async_set_volume_level(self, volume: float) -> None:
        db = VOLUME_DB_MIN + volume * VOLUME_DB_SPAN
        await self.coordinator.client.set_volume_db(self._zone_id, db)
        await self.coordinator.async_request_refresh()

    async def async_select_source(self, source: str) -> None:
        device = self.coordinator.data.device
        input_id = next(
            (k for k, v in device.input_names.items() if v == source), source
        )
        await self.coordinator.client.set_input(self._zone_id, input_id)
        await self.coordinator.async_request_refresh()
