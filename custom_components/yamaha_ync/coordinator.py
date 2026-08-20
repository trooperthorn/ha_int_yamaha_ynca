"""Push-first coordinator: UPnP events drive updates, polling is the backstop."""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .client import YncClient, YncConnectionError
from .const import BACKSTOP_POLL_INTERVAL_SECONDS, DOMAIN
from .models import DeviceInfo, ZoneCapabilities, ZoneStatus
from .notify_listener import YncEvent, YncNotifyListener

_LOGGER = logging.getLogger(__name__)


@dataclass
class ZoneState:
    capabilities: ZoneCapabilities
    status: ZoneStatus = field(default_factory=ZoneStatus)


@dataclass
class YncData:
    device: DeviceInfo
    zones: dict[str, ZoneState]


class YncCoordinator(DataUpdateCoordinator[YncData]):
    """One coordinator per receiver, fanning out to every configured zone."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry, client: YncClient) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN}:{client.host}",
            update_interval=timedelta(seconds=BACKSTOP_POLL_INTERVAL_SECONDS),
        )
        self.client = client
        self._entry = entry
        self._listener = YncNotifyListener(self._handle_event)

    async def async_start_push(self) -> None:
        await self._listener.start()

    async def async_stop_push(self) -> None:
        await self._listener.stop()

    def _handle_event(self, event: YncEvent) -> None:
        """Fired from the UDP listener the instant the receiver reports a change.

        We don't trust the event payload for the new value (the spec only
        promises *which* property changed, not to what) -- we schedule a
        targeted refresh of just that zone instead of a full-device poll.
        """
        self.hass.async_create_task(self._async_refresh_zone(event.zone_id))

    async def _async_refresh_zone(self, zone_id: str) -> None:
        if self.data is None or zone_id not in self.data.zones:
            return
        try:
            status = await self.client.get_zone_status(zone_id)
        except YncConnectionError as err:
            _LOGGER.debug("Push-triggered refresh of %s failed: %s", zone_id, err)
            return
        self.data.zones[zone_id].status = status
        self.async_set_updated_data(self.data)

    async def _async_update_data(self) -> YncData:
        """The slow backstop poll -- runs regardless of whether push is working."""
        try:
            if self.data is None:
                device = await self.client.get_device_info()
                zones: dict[str, ZoneState] = {}
                for zone_id in device.zones:
                    capabilities = await self.client.get_zone_capabilities(zone_id)
                    zones[zone_id] = ZoneState(capabilities=capabilities)
            else:
                device = self.data.device
                zones = self.data.zones

            # A single Basic_Status GET returns the push-backed properties
            # (Power/Input/Volume/Play_Info) and the deep AVENTAGE-specific
            # fields (HDMI, dialogue, tone, etc.) together, so one poll
            # cadence covers both -- no separate "deep poll" tier needed
            # unless a future field (e.g. a FuncTag_List decode) needs its
            # own, slower schedule.
            for zone_id, zone in zones.items():
                zone.status = await self.client.get_zone_status(zone_id)
        except YncConnectionError as err:
            raise UpdateFailed(f"Could not reach {self.client.host}: {err}") from err

        return YncData(device=device, zones=zones)
