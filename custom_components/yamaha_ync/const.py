"""Constants for the Yamaha AV Receiver (YNC) integration."""
from __future__ import annotations

DOMAIN = "yamaha_ync"

CONF_HOST = "host"

DEFAULT_PORT = 80
CTRL_PATH = "/YamahaRemoteControl/ctrl"

# UPnP event stream, per Yamaha's "Overview of YNC / YRSC" spec section 4.4.3.
SSDP_MULTICAST_ADDR = "239.255.255.250"
SSDP_MULTICAST_PORT = 1900
YNC_EVENT_NT = "urn:yamaha-com:service:YamahaRemoteControl:2"
YNC_EVENT_NTS = "yamaha:propchange"

# The spec's own recommendation: event notifications aren't guaranteed to
# arrive, so poll these same four properties at a slow cadence as a backstop.
# A single Basic_Status GET returns them alongside every deep AVENTAGE-
# specific field in the same call, so one interval covers the whole zone.
PUSH_BACKED_PROPERTIES = ("Power", "Input", "Volume", "Play_Info")
BACKSTOP_POLL_INTERVAL_SECONDS = 60

# Zone id (as used in entity unique_ids / HA device slugs) -> XML node name.
ZONE_XML_NODES: dict[str, str] = {
    "main": "Main_Zone",
    "zone2": "Zone_2",
    "zone3": "Zone_3",
    "zone4": "Zone_4",
}
ZONE_DISPLAY_NAMES: dict[str, str] = {
    "main": "Main Zone",
    "zone2": "Zone 2",
    "zone3": "Zone 3",
    "zone4": "Zone 4",
}

MANUFACTURER = "Yamaha"
