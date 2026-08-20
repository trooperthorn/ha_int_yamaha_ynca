"""Device triggers: react to a specific zone event, not a generic state change.

Exists so an automation built in the UI can say "when this zone powers on"
or "when this zone's input changes" directly, instead of a hand-rolled
template trigger against a state string -- meaningful now that the push
listener (notify_listener.py) can make these fire within moments of the
real-world change, not a poll cycle later.
"""
from __future__ import annotations

import voluptuous as vol
from homeassistant.components.device_automation import DEVICE_TRIGGER_BASE_SCHEMA
from homeassistant.components.homeassistant.triggers import state as state_trigger
from homeassistant.const import CONF_DEVICE_ID, CONF_DOMAIN, CONF_PLATFORM, CONF_TYPE
from homeassistant.core import CALLBACK_TYPE, HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.trigger import TriggerActionType, TriggerInfo

from .const import DOMAIN

TRIGGER_TYPE_POWERED_ON = "zone_powered_on"
TRIGGER_TYPE_POWERED_OFF = "zone_powered_off"
TRIGGER_TYPE_INPUT_CHANGED = "input_changed"

TRIGGER_TYPES = {
    TRIGGER_TYPE_POWERED_ON,
    TRIGGER_TYPE_POWERED_OFF,
    TRIGGER_TYPE_INPUT_CHANGED,
}

# Which platform/unique_id-suffix each trigger type watches, and (for the
# power triggers) which state it's watching for.
_TRIGGER_ENTITY_SUFFIX = {
    TRIGGER_TYPE_POWERED_ON: "_media_player",
    TRIGGER_TYPE_POWERED_OFF: "_media_player",
    TRIGGER_TYPE_INPUT_CHANGED: "_input_title",
}
_TRIGGER_TO_STATE = {
    TRIGGER_TYPE_POWERED_ON: "on",
    TRIGGER_TYPE_POWERED_OFF: "off",
}

TRIGGER_SCHEMA = DEVICE_TRIGGER_BASE_SCHEMA.extend(
    {vol.Required(CONF_TYPE): vol.In(TRIGGER_TYPES)}
)


def _find_entity_id(hass: HomeAssistant, device_id: str, suffix: str) -> str | None:
    registry = er.async_get(hass)
    for entry in er.async_entries_for_device(registry, device_id):
        if entry.unique_id.endswith(suffix):
            return entry.entity_id
    return None


async def async_get_triggers(hass: HomeAssistant, device_id: str) -> list[dict]:
    registry = er.async_get(hass)
    entries = er.async_entries_for_device(registry, device_id)
    if not any(entry.platform == DOMAIN for entry in entries):
        return []

    triggers = []
    for trigger_type, suffix in _TRIGGER_ENTITY_SUFFIX.items():
        if _find_entity_id(hass, device_id, suffix) is not None:
            triggers.append(
                {
                    CONF_PLATFORM: "device",
                    CONF_DEVICE_ID: device_id,
                    CONF_DOMAIN: DOMAIN,
                    CONF_TYPE: trigger_type,
                }
            )
    return triggers


async def async_attach_trigger(
    hass: HomeAssistant,
    config: dict,
    action: TriggerActionType,
    trigger_info: TriggerInfo,
) -> CALLBACK_TYPE:
    trigger_type = config[CONF_TYPE]
    entity_id = _find_entity_id(
        hass, config[CONF_DEVICE_ID], _TRIGGER_ENTITY_SUFFIX[trigger_type]
    )
    if entity_id is None:
        raise ValueError(
            f"No entity found on this device for trigger type {trigger_type}"
        )

    state_config = {
        state_trigger.CONF_PLATFORM: "state",
        state_trigger.CONF_ENTITY_ID: [entity_id],
    }
    to_state = _TRIGGER_TO_STATE.get(trigger_type)
    if to_state is not None:
        state_config[state_trigger.CONF_TO] = to_state

    state_config = state_trigger.TRIGGER_SCHEMA(state_config)
    return await state_trigger.async_attach_trigger(
        hass, state_config, action, trigger_info, platform_type="device"
    )
