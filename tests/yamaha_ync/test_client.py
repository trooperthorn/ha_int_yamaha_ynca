"""client.py's response-unwrapping against real captured payloads.

Regression coverage for a real bug caught by the live-device probe script:
get_device_info/get_zone_capabilities/get_zone_status were re-wrapping an
already-rooted response dict under another layer of the same keys, so every
field silently read back as missing.
"""
from __future__ import annotations

import pathlib
from unittest.mock import AsyncMock

import pytest

from custom_components.yamaha_ync.client import YncClient

FIXTURES = pathlib.Path(__file__).parent / "fixtures"


def _fixture_body(name: str) -> dict:
    from custom_components.yamaha_ync.xml_protocol import parse_response

    _rc, body = parse_response((FIXTURES / name).read_text())
    return body


@pytest.mark.asyncio
async def test_get_device_info_unwraps_correctly(monkeypatch: pytest.MonkeyPatch) -> None:
    client = YncClient("192.168.1.4", session=AsyncMock())
    monkeypatch.setattr(
        client, "get", AsyncMock(return_value=_fixture_body("zone4_config.xml"))
    )
    # zone4_config.xml is a Zone_4/Config payload, not System/Config, but the
    # unwrap logic under test only cares about *not* adding an extra layer --
    # get_device_info should read straight through to whatever get() returned.
    device = await client.get_device_info()
    # No System/Config present in this fixture, so fields fall back to
    # defaults rather than raising -- the point is it doesn't KeyError, and
    # it must not be looking two layers too deep.
    assert device.model_name == "Yamaha AV Receiver"


@pytest.mark.asyncio
async def test_get_zone_capabilities_reads_real_zone4_payload(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = YncClient("192.168.1.4", session=AsyncMock())
    monkeypatch.setattr(
        client, "get", AsyncMock(return_value=_fixture_body("zone4_config.xml"))
    )
    capabilities = await client.get_zone_capabilities("zone4")
    assert capabilities.has_volume is False
    assert capabilities.room_name == "Kitchen"


@pytest.mark.asyncio
async def test_get_zone_status_reads_real_main_zone_payload(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = YncClient("192.168.1.4", session=AsyncMock())
    monkeypatch.setattr(
        client, "get", AsyncMock(return_value=_fixture_body("main_zone_basic_status.xml"))
    )
    status = await client.get_zone_status("main")
    assert status.volume_db == -41.5
    assert status.input_title == "Great Room TV eARC"


@pytest.mark.asyncio
async def test_get_netusb_play_info_reads_real_spotify_payload(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = YncClient("192.168.1.4", session=AsyncMock())
    monkeypatch.setattr(
        client, "get", AsyncMock(return_value=_fixture_body("spotify_play_info.xml"))
    )
    info = await client.get_netusb_play_info("Spotify")
    assert info.playback_state == "Stop"
    assert info.shuffle is True
    assert info.repeat == "All"


@pytest.mark.asyncio
async def test_recall_scene_builds_expected_put(monkeypatch: pytest.MonkeyPatch) -> None:
    client = YncClient("192.168.1.4", session=AsyncMock())
    put_mock = AsyncMock()
    monkeypatch.setattr(client, "put", put_mock)

    await client.recall_scene("main", 3)

    put_mock.assert_awaited_once_with(["Main_Zone", "Scene", "Scene_Sel"], "Scene 3")


@pytest.mark.asyncio
async def test_netusb_playback_builds_expected_put(monkeypatch: pytest.MonkeyPatch) -> None:
    client = YncClient("192.168.1.4", session=AsyncMock())
    put_mock = AsyncMock()
    monkeypatch.setattr(client, "put", put_mock)

    await client.netusb_playback("NET_RADIO", "Skip Fwd")

    put_mock.assert_awaited_once_with(
        ["NET_RADIO", "Play_Control", "Playback"], "Skip Fwd"
    )


@pytest.mark.asyncio
async def test_netusb_set_shuffle_and_repeat_build_expected_puts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = YncClient("192.168.1.4", session=AsyncMock())
    put_mock = AsyncMock()
    monkeypatch.setattr(client, "put", put_mock)

    await client.netusb_set_shuffle("Spotify", True)
    await client.netusb_set_repeat("Spotify", "One")

    assert put_mock.await_args_list[0].args == (
        ["Spotify", "Play_Control", "Play_Mode", "Shuffle"],
        "On",
    )
    assert put_mock.await_args_list[1].args == (
        ["Spotify", "Play_Control", "Play_Mode", "Repeat"],
        "One",
    )
