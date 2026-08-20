"""Stand-alone, read-only validation of client.py against a real receiver.

Usage:
    python scripts/probe_device.py 192.168.1.4

Only ever issues GET requests -- this is for proving the client and models
work against live hardware, not for exercising PUT commands against
someone's actual AV equipment.
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# Reuse the same parent-package stub trick as tests/conftest.py so this
# script can run without a full Home Assistant install.
import types

for name, path in (
    ("custom_components", Path(__file__).resolve().parent.parent / "custom_components"),
    (
        "custom_components.yamaha_ync",
        Path(__file__).resolve().parent.parent / "custom_components" / "yamaha_ync",
    ),
):
    if name not in sys.modules:
        module = types.ModuleType(name)
        module.__path__ = [str(path)]
        sys.modules[name] = module

import aiohttp

from custom_components.yamaha_ync.client import YncClient


async def main(host: str) -> None:
    async with aiohttp.ClientSession() as session:
        client = YncClient(host, session)

        print(f"GET System/Config from {host} ...")
        device = await client.get_device_info()
        print(f"  model_name  = {device.model_name}")
        print(f"  system_id   = {device.system_id}")
        print(f"  version     = {device.version}")
        print(f"  zones       = {device.zones}")
        print(f"  input count = {len(device.input_names)}")

        for zone_id in device.zones:
            print(f"\nGET {zone_id}/Config + Basic_Status ...")
            capabilities = await client.get_zone_capabilities(zone_id)
            status = await client.get_zone_status(zone_id)
            print(f"  has_volume  = {capabilities.has_volume}")
            print(f"  room_name   = {capabilities.room_name}")
            print(f"  power       = {status.power}")
            print(f"  input_id    = {status.input_id}")
            print(f"  input_title = {status.input_title}")
            if status.volume_db is not None:
                print(f"  volume_db   = {status.volume_db}")
            if status.hdmi_outputs:
                print(f"  hdmi_outputs= {status.hdmi_outputs}")

        print("\nAll reads succeeded -- client.py and models.py work against real hardware.")


if __name__ == "__main__":
    target_host = sys.argv[1] if len(sys.argv) > 1 else "192.168.1.4"
    asyncio.run(main(target_host))
