"""Listener for the receiver's UPnP NOTIFY push events.

Per the "Overview of YNC / YRSC" spec (4.4.3), the device multicasts a GENA-
style NOTIFY packet to 239.255.255.250:1900 the instant Power, Input, Volume,
or Play_Info changes in any zone:

    NOTIFY * HTTP/1.1
    Host: 239.255.255.250:1900
    NT: urn:yamaha-com:service:YamahaRemoteControl:2
    NTS: yamaha:propchange
    USN: uuid:<UUID>::urn:yamaha-com:service:YamahaRemoteControl:2

    <YAMAHA_AV cmd="EVENT"><Main_Zone><Property>Power</Property></Main_Zone></YAMAHA_AV>

No existing Home Assistant integration for this device family listens for
this -- they all poll instead. This is the piece that makes local_push
possible on the plain HTTP/XML transport, no YNCA/MusicCast dependency
required.

The spec explicitly warns delivery isn't guaranteed ("it is recommended that
the Controller poll...since it is NOT guaranteed for Event Notification
commands to be surely delivered"), so callers should still run a slow
backstop poll (see coordinator.py) rather than trusting this exclusively.
"""
from __future__ import annotations

import asyncio
import logging
import socket
from collections.abc import Callable
from dataclasses import dataclass
from xml.etree import ElementTree as ET

from .const import (
    SSDP_MULTICAST_ADDR,
    SSDP_MULTICAST_PORT,
    YNC_EVENT_NT,
    YNC_EVENT_NTS,
    ZONE_XML_NODES,
)

_LOGGER = logging.getLogger(__name__)

_XML_NODE_TO_ZONE = {v: k for k, v in ZONE_XML_NODES.items()}


@dataclass(frozen=True)
class YncEvent:
    """One "something changed" notification from the receiver."""

    zone_id: str
    property_name: str


def _parse_notify_datagram(raw: bytes) -> YncEvent | None:
    """Return a YncEvent if `raw` is a Yamaha propchange NOTIFY, else None."""
    try:
        text = raw.decode("utf-8", errors="replace")
    except Exception:  # noqa: BLE001 - malformed datagram, never crash the listener
        return None

    if "\r\n\r\n" in text:
        head, _, body = text.partition("\r\n\r\n")
    else:
        head, body = text, ""

    lines = head.split("\r\n")
    if not lines or not lines[0].upper().startswith("NOTIFY"):
        return None

    headers = {}
    for line in lines[1:]:
        if ":" not in line:
            continue
        key, _, value = line.partition(":")
        headers[key.strip().upper()] = value.strip()

    if headers.get("NT") != YNC_EVENT_NT or headers.get("NTS") != YNC_EVENT_NTS:
        return None

    if not body.strip():
        return None

    try:
        root = ET.fromstring(body.strip())
    except ET.ParseError:
        _LOGGER.debug("Malformed YNC event body: %r", body)
        return None

    for zone_element in root:
        zone_id = _XML_NODE_TO_ZONE.get(zone_element.tag)
        if zone_id is None:
            continue
        prop_element = zone_element.find("Property")
        if prop_element is not None and prop_element.text:
            return YncEvent(zone_id=zone_id, property_name=prop_element.text.strip())
    return None


class _NotifyProtocol(asyncio.DatagramProtocol):
    def __init__(self, callback: Callable[[YncEvent], None]) -> None:
        self._callback = callback

    def datagram_received(self, data: bytes, addr) -> None:
        event = _parse_notify_datagram(data)
        if event is not None:
            _LOGGER.debug("YNC event from %s: %s", addr, event)
            self._callback(event)


def _build_multicast_socket() -> socket.socket:
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    if hasattr(socket, "SO_REUSEPORT"):
        try:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
        except OSError:
            pass  # not available on this platform; SO_REUSEADDR is enough on Windows
    sock.bind(("", SSDP_MULTICAST_PORT))
    group = socket.inet_aton(SSDP_MULTICAST_ADDR)
    mreq = group + socket.inet_aton("0.0.0.0")
    sock.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq)
    sock.setblocking(False)
    return sock


class YncNotifyListener:
    """Owns the multicast socket for the lifetime of a config entry."""

    def __init__(self, callback: Callable[[YncEvent], None]) -> None:
        self._callback = callback
        self._transport: asyncio.DatagramTransport | None = None

    async def start(self) -> None:
        loop = asyncio.get_running_loop()
        sock = await loop.run_in_executor(None, _build_multicast_socket)
        self._transport, _ = await loop.create_datagram_endpoint(
            lambda: _NotifyProtocol(self._callback), sock=sock
        )
        _LOGGER.debug(
            "Listening for YNC push events on %s:%s",
            SSDP_MULTICAST_ADDR,
            SSDP_MULTICAST_PORT,
        )

    async def stop(self) -> None:
        if self._transport is not None:
            self._transport.close()
            self._transport = None
