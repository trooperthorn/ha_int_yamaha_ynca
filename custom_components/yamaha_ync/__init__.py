"""The Yamaha AV Receiver (YNC) integration."""
from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .client import YncClient
from .coordinator import YncCoordinator

PLATFORMS: list[Platform] = [
    Platform.MEDIA_PLAYER,
    Platform.REMOTE,
    Platform.NUMBER,
    Platform.SELECT,
    Platform.SWITCH,
    Platform.BINARY_SENSOR,
    Platform.SENSOR,
]

type YamahaYncConfigEntry = ConfigEntry[YncCoordinator]


async def async_setup_entry(hass: HomeAssistant, entry: YamahaYncConfigEntry) -> bool:
    session = async_get_clientsession(hass)
    client = YncClient(entry.data[CONF_HOST], session)
    coordinator = YncCoordinator(hass, entry, client)

    await coordinator.async_config_entry_first_refresh()
    await coordinator.async_start_push()

    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: YamahaYncConfigEntry) -> bool:
    await entry.runtime_data.async_stop_push()
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
