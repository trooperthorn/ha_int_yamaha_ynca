"""Diagnostics: dump coordinator state for bug reports, host address redacted."""
from __future__ import annotations

from dataclasses import asdict
from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant

TO_REDACT = {CONF_HOST}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    coordinator = entry.runtime_data
    data = coordinator.data
    return {
        "entry_data": async_redact_data(dict(entry.data), TO_REDACT),
        "device": asdict(data.device),
        "zones": {
            zone_id: {
                "capabilities": asdict(zone.capabilities),
                "status": asdict(zone.status),
            }
            for zone_id, zone in data.zones.items()
        },
    }
