"""Async client for the Yamaha YNC (YAMAHA_AV) HTTP/XML control API."""
from __future__ import annotations

import asyncio
import logging

import aiohttp

from .const import CTRL_PATH, ZONE_XML_NODES
from .models import DeviceInfo, ZoneCapabilities, ZoneStatus
from .xml_protocol import build_get, build_put, parse_response

_LOGGER = logging.getLogger(__name__)

REQUEST_TIMEOUT = aiohttp.ClientTimeout(total=10)


class YncClient:
    """Thin async wrapper around one receiver's /YamahaRemoteControl/ctrl.

    Per the protocol spec, the device processes one request at a time and
    the controller "shall not send the next request packet until a response
    packet or NAK packet is returned" -- so every call funnels through a
    single lock rather than relying on the caller to serialize itself.
    """

    def __init__(self, host: str, session: aiohttp.ClientSession) -> None:
        self._host = host
        self._session = session
        self._url = f"http://{host}{CTRL_PATH}"
        self._lock = asyncio.Lock()

    @property
    def host(self) -> str:
        return self._host

    async def _send(self, body: str) -> dict:
        async with self._lock:
            try:
                async with self._session.post(
                    self._url,
                    data=body.encode("utf-8"),
                    headers={"Content-Type": "text/xml; charset=utf-8"},
                    timeout=REQUEST_TIMEOUT,
                ) as resp:
                    resp.raise_for_status()
                    text = await resp.text()
            except aiohttp.ClientError as err:
                raise YncConnectionError(str(err)) from err
            except asyncio.TimeoutError as err:
                raise YncConnectionError("timed out talking to receiver") from err

        _rc, parsed = parse_response(text)
        return parsed

    async def get(self, path: list[str]) -> dict:
        return await self._send(build_get(path))

    async def put(self, path: list[str], value: str) -> None:
        await self._send(build_put(path, value))

    # -- convenience wrappers over the confirmed function-tree paths ------

    async def get_device_info(self) -> DeviceInfo:
        # get() returns the full tree rooted at YAMAHA_AV's children, i.e.
        # already shaped as {"System": {"Config": {...}}} -- pass it through
        # as-is rather than re-wrapping it under another "System"/"Config".
        body = await self.get(["System", "Config"])
        return DeviceInfo.from_response(body)

    async def get_zone_capabilities(self, zone_id: str) -> ZoneCapabilities:
        node = ZONE_XML_NODES[zone_id]
        body = await self.get([node, "Config"])
        return ZoneCapabilities.from_response(body[node])

    async def get_zone_status(self, zone_id: str) -> ZoneStatus:
        node = ZONE_XML_NODES[zone_id]
        body = await self.get([node, "Basic_Status"])
        return ZoneStatus.from_response(body[node])

    async def set_power(self, zone_id: str, on: bool) -> None:
        node = ZONE_XML_NODES[zone_id]
        await self.put([node, "Power_Control", "Power"], "On" if on else "Standby")

    async def set_mute(self, zone_id: str, mute: bool) -> None:
        node = ZONE_XML_NODES[zone_id]
        await self.put([node, "Volume", "Mute"], "On" if mute else "Off")

    async def set_volume_db(self, zone_id: str, db: float) -> None:
        """Volume is set in 0.5 dB steps, encoded as tenths of a dB."""
        node = ZONE_XML_NODES[zone_id]
        stepped = round(db * 2) / 2
        await self.put([node, "Volume", "Lvl", "Val"], str(int(stepped * 10)))

    async def set_input(self, zone_id: str, input_id: str) -> None:
        node = ZONE_XML_NODES[zone_id]
        await self.put([node, "Input", "Input_Sel"], input_id)

    async def set_party_mode(self, zone_id: str, on: bool) -> None:
        node = ZONE_XML_NODES[zone_id]
        await self.put([node, "Party_Info"], "On" if on else "Off")

    async def set_pure_direct(self, zone_id: str, on: bool) -> None:
        node = ZONE_XML_NODES[zone_id]
        await self.put(
            [node, "Sound_Video", "Pure_Direct", "Mode"], "On" if on else "Off"
        )

    async def set_hdmi_output(self, zone_id: str, output_id: str, on: bool) -> None:
        node = ZONE_XML_NODES[zone_id]
        await self.put(
            [node, "Sound_Video", "HDMI", "Output", output_id], "On" if on else "Off"
        )

    async def set_dialogue_lift(self, zone_id: str, level: int) -> None:
        node = ZONE_XML_NODES[zone_id]
        await self.put(
            [node, "Sound_Video", "Dialogue_Adjust", "Dialogue_Lift"], str(level)
        )

    async def set_dialogue_level(self, zone_id: str, level: int) -> None:
        node = ZONE_XML_NODES[zone_id]
        await self.put(
            [node, "Sound_Video", "Dialogue_Adjust", "Dialogue_Lvl"], str(level)
        )

    async def set_dts_dialogue_control(self, zone_id: str, level: int) -> None:
        node = ZONE_XML_NODES[zone_id]
        await self.put(
            [node, "Sound_Video", "Dialogue_Adjust", "DTS_Dialogue_Control"],
            str(level),
        )

    async def set_ypao_volume(self, zone_id: str, value: str) -> None:
        node = ZONE_XML_NODES[zone_id]
        await self.put([node, "Sound_Video", "YPAO_Volume"], value)

    async def set_extra_bass(self, zone_id: str, value: str) -> None:
        node = ZONE_XML_NODES[zone_id]
        await self.put([node, "Sound_Video", "Extra_Bass"], value)

    async def set_adaptive_drc(self, zone_id: str, value: str) -> None:
        node = ZONE_XML_NODES[zone_id]
        await self.put([node, "Sound_Video", "Adaptive_DRC"], value)

    async def set_subwoofer_trim_db(self, zone_id: str, db: float) -> None:
        node = ZONE_XML_NODES[zone_id]
        stepped = round(db * 2) / 2
        await self.put(
            [node, "Volume", "Subwoofer_Trim", "Val"], str(int(stepped * 10))
        )


class YncConnectionError(Exception):
    """Raised when the receiver can't be reached or errors at the transport layer."""
