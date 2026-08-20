"""Passively listen for real UPnP NOTIFY push events for a short window.

Usage:
    python scripts/listen_notify.py [seconds]

Read-only: joins the multicast group and reports whatever arrives. Doesn't
change the receiver's state, so it can only observe events triggered by
something else (the physical remote, the MusicCast app, etc.) during the
listen window -- a quiet window with a receiver nobody's touching is
inconclusive, not a failure.
"""
from __future__ import annotations

import asyncio
import sys
import types
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
for name, path in (
    ("custom_components", ROOT / "custom_components"),
    ("custom_components.yamaha_ync", ROOT / "custom_components" / "yamaha_ync"),
):
    if name not in sys.modules:
        module = types.ModuleType(name)
        module.__path__ = [str(path)]
        sys.modules[name] = module

from custom_components.yamaha_ync.notify_listener import YncNotifyListener


async def main(seconds: float) -> None:
    events = []

    def on_event(event) -> None:
        print(f"  EVENT: zone={event.zone_id} property={event.property_name}")
        events.append(event)

    listener = YncNotifyListener(on_event)
    print(f"Joining 239.255.255.250:1900 and listening for {seconds:.0f}s ...")
    await listener.start()
    try:
        await asyncio.sleep(seconds)
    finally:
        await listener.stop()

    if events:
        print(f"\nCaptured {len(events)} event(s) -- push path confirmed live.")
    else:
        print(
            "\nNo events captured in this window. Inconclusive, not a failure -- "
            "nothing on the receiver changed state while listening. Retry while "
            "changing volume/input from the physical remote or the MusicCast app."
        )


if __name__ == "__main__":
    duration = float(sys.argv[1]) if len(sys.argv) > 1 else 20.0
    asyncio.run(main(duration))
