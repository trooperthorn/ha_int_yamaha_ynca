"""One media_player entity per configured zone."""
from __future__ import annotations

from datetime import datetime

from homeassistant.components.media_player import (
    MediaPlayerDeviceClass,
    MediaPlayerEntity,
    MediaPlayerEntityFeature,
    MediaPlayerState,
    RepeatMode,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import dt as dt_util

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
from .models import NetUsbPlayInfo

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
VOLUME_STEP_DB = 1.0

_REPEAT_TO_HA = {"off": RepeatMode.OFF, "one": RepeatMode.ONE, "all": RepeatMode.ALL}
_REPEAT_TO_DEVICE = {
    RepeatMode.OFF: "Off",
    RepeatMode.ONE: "One",
    RepeatMode.ALL: "All",
}

_PLAYBACK_TO_STATE = {
    "play": MediaPlayerState.PLAYING,
    "pause": MediaPlayerState.PAUSED,
    "stop": MediaPlayerState.IDLE,
}


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
                | MediaPlayerEntityFeature.VOLUME_STEP
            )
        if self.coordinator.data.device.input_names:
            features |= MediaPlayerEntityFeature.SELECT_SOURCE
        # PLAY/PAUSE/STOP/NEXT/PREVIOUS and shuffle/repeat only make sense
        # once the zone is actually parked on a netusb-family source -- the
        # features are declared unconditionally (matching how `source_list`
        # covers every input the zone could ever be switched to, not just
        # today's), and the transport methods below raise if called while
        # on a source that has no Play_Control at all.
        features |= (
            MediaPlayerEntityFeature.PLAY
            | MediaPlayerEntityFeature.PAUSE
            | MediaPlayerEntityFeature.STOP
            | MediaPlayerEntityFeature.NEXT_TRACK
            | MediaPlayerEntityFeature.PREVIOUS_TRACK
            | MediaPlayerEntityFeature.SHUFFLE_SET
            | MediaPlayerEntityFeature.REPEAT_SET
        )
        self._attr_supported_features = features
        self._attr_source_list = sorted(self.coordinator.data.device.input_names.values())

    @property
    def _media(self) -> NetUsbPlayInfo | None:
        return self._zone.media

    @property
    def _on_netusb_source(self) -> bool:
        return self._zone.status.input_id in NETUSB_FAMILY_INPUTS

    @property
    def state(self) -> MediaPlayerState | None:
        power = self._zone.status.power
        if power is None:
            return None
        if not power:
            return MediaPlayerState.OFF
        media = self._media
        if media is not None and media.playback_state:
            mapped = _PLAYBACK_TO_STATE.get(media.playback_state.lower())
            if mapped is not None:
                return mapped
        return MediaPlayerState.ON

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

    @property
    def media_title(self) -> str | None:
        media = self._media
        if media is None:
            return None
        return media.title or media.station

    @property
    def media_artist(self) -> str | None:
        return self._media.artist if self._media else None

    @property
    def media_album_name(self) -> str | None:
        return self._media.album if self._media else None

    @property
    def media_channel(self) -> str | None:
        return self._media.station if self._media else None

    @property
    def media_duration(self) -> int | None:
        return self._media.total_seconds if self._media else None

    @property
    def media_position(self) -> int | None:
        return self._media.elapsed_seconds if self._media else None

    @property
    def media_position_updated_at(self) -> datetime | None:
        if self._media is None or self._media.elapsed_seconds is None:
            return None
        return dt_util.utcnow()

    @property
    def media_image_url(self) -> str | None:
        return self._media.album_art_url if self._media else None

    @property
    def shuffle(self) -> bool | None:
        return self._media.shuffle if self._media else None

    @property
    def repeat(self) -> RepeatMode | None:
        if self._media is None or self._media.repeat is None:
            return None
        return _REPEAT_TO_HA.get(self._media.repeat.lower())

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

    async def async_volume_up(self) -> None:
        current = self._zone.status.volume_db
        if current is not None:
            await self.coordinator.client.set_volume_db(
                self._zone_id, min(VOLUME_DB_MAX, current + VOLUME_STEP_DB)
            )
            await self.coordinator.async_request_refresh()

    async def async_volume_down(self) -> None:
        current = self._zone.status.volume_db
        if current is not None:
            await self.coordinator.client.set_volume_db(
                self._zone_id, max(VOLUME_DB_MIN, current - VOLUME_STEP_DB)
            )
            await self.coordinator.async_request_refresh()

    async def async_select_source(self, source: str) -> None:
        device = self.coordinator.data.device
        input_id = next(
            (k for k, v in device.input_names.items() if v == source), source
        )
        await self.coordinator.client.set_input(self._zone_id, input_id)
        await self.coordinator.async_request_refresh()

    async def async_media_play(self) -> None:
        await self._async_playback(PLAYBACK_PLAY)

    async def async_media_pause(self) -> None:
        await self._async_playback(PLAYBACK_PAUSE)

    async def async_media_stop(self) -> None:
        await self._async_playback(PLAYBACK_STOP)

    async def async_media_next_track(self) -> None:
        await self._async_playback(PLAYBACK_SKIP_FWD)

    async def async_media_previous_track(self) -> None:
        await self._async_playback(PLAYBACK_SKIP_REV)

    async def _async_playback(self, command: str) -> None:
        if not self._on_netusb_source:
            return
        await self.coordinator.client.netusb_playback(
            self._zone.status.input_id, command
        )
        await self.coordinator.async_request_refresh()

    async def async_set_shuffle(self, shuffle: bool) -> None:
        if not self._on_netusb_source:
            return
        await self.coordinator.client.netusb_set_shuffle(
            self._zone.status.input_id, shuffle
        )
        await self.coordinator.async_request_refresh()

    async def async_set_repeat(self, repeat: RepeatMode) -> None:
        if not self._on_netusb_source:
            return
        device_value = _REPEAT_TO_DEVICE.get(repeat)
        if device_value is None:
            return
        await self.coordinator.client.netusb_set_repeat(
            self._zone.status.input_id, device_value
        )
        await self.coordinator.async_request_refresh()
