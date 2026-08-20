"""Config-flow, setup/unload, and coordinator behavior against a real `hass`.

Requires the `hass` fixture from `pytest-homeassistant-custom-component`,
which needs a working asyncio event loop of the kind pytest-socket blocks
on native Windows (see tests/yamaha_ync/conftest.py) -- written and reviewed
carefully but not executable against Windows locally; this repo's existing
CI (.github/workflows/validations.yaml, ubuntu-latest) is what actually
verifies it.

The `auto_enable_custom_integrations` fixture below duplicates what the
repo's root tests/conftest.py already provides autouse -- kept here anyway
since this file was originally written to run standalone against a bare
custom_components/yamaha_ync tree, and a second request for the same
fixture is harmless.
"""
from __future__ import annotations

from unittest.mock import AsyncMock, Mock, patch

import pytest
from homeassistant import config_entries
from homeassistant.config_entries import ConfigEntryState
from homeassistant.data_entry_flow import FlowResultType
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.yamaha_ync.client import YncConnectionError
from custom_components.yamaha_ync.const import DOMAIN
from custom_components.yamaha_ync.models import DeviceInfo, ZoneCapabilities, ZoneStatus

FAKE_DEVICE = DeviceInfo(
    model_name="RX-A3080",
    system_id="0B3961F3",
    version="2.16/3.14",
    zones=["main"],
    input_names={"AUDIO_3": "Great Room TV eARC"},
)


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    """Let hass's component loader see custom_components/yamaha_ync.

    Scoped to this file rather than a global conftest.py fixture: pulling
    in the `enable_custom_integrations` fixture unconditionally would load
    the whole pytest-homeassistant-custom-component plugin for every test
    in the suite, including the lightweight protocol-layer tests that are
    meant to run without it (see conftest.py's docstring).
    """
    yield


@pytest.fixture(autouse=True)
def mock_get_device_info():
    with patch(
        "custom_components.yamaha_ync.client.YncClient.get_device_info",
        AsyncMock(return_value=FAKE_DEVICE),
    ) as mocked:
        yield mocked


@pytest.fixture(autouse=True)
def mock_clientsession():
    """Never construct a real aiohttp ClientSession in these tests.

    `_async_probe` in config_flow.py calls the real
    `async_get_clientsession(hass)` before handing the session to `YncClient`
    -- even with `get_device_info` mocked, building that real session lazily
    initializes aiohttp's pycares-based DNS resolver, which spawns a
    background thread the harness's teardown-time thread-leak check has no
    opt-out for (unlike its lingering-task/-timer checks). Mocking the
    session constructor itself, the way HA's own test suite does, avoids
    ever touching that machinery.
    """
    with (
        patch(
            "custom_components.yamaha_ync.config_flow.async_get_clientsession",
            return_value=Mock(),
        ),
        patch(
            "custom_components.yamaha_ync.async_get_clientsession",
            return_value=Mock(),
        ),
    ):
        yield


@pytest.fixture
def bypass_entry_setup():
    """Stop a flow-only test's newly-created/updated entry from actually
    being set up for real.

    Creating (or reconfiguring) a config entry via `hass.config_entries.flow`
    isn't just a flow-level event -- HA follows through and calls this
    integration's real `async_setup_entry`, which reaches the network via
    `get_zone_capabilities`/`get_zone_status`. `pytest-socket` correctly
    blocks that, but the resulting failed coordinator refresh schedules a
    retry timer that's still pending at test teardown, which trips the test
    harness's own leaked-background-work assertion. `async_unload_entry`
    needs bypassing too, for a related reason: with setup faked out,
    `entry.runtime_data` (the coordinator) was never assigned, so the
    harness's own automatic teardown-time unload would otherwise crash on
    `entry.runtime_data.async_stop_push()`. `test_setup_and_unload_entry`
    below exercises the real setup/unload path (with everything it needs
    mocked); these flow-focused tests only care about the flow's outcome.
    """
    with (
        patch("custom_components.yamaha_ync.async_setup_entry", return_value=True),
        patch("custom_components.yamaha_ync.async_unload_entry", return_value=True),
    ):
        yield


async def test_user_flow_creates_entry(hass, bypass_entry_setup) -> None:
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"host": "192.168.1.4"}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "RX-A3080"
    assert result["data"] == {"host": "192.168.1.4"}

    # Let anything the (bypassed-but-still-triggered) setup scheduled
    # actually settle before the test returns, so the harness's teardown-
    # time background-work check isn't racing it.
    await hass.async_block_till_done()


async def test_user_flow_cannot_connect_shows_error(
    hass, mock_get_device_info: AsyncMock
) -> None:
    mock_get_device_info.side_effect = YncConnectionError("unreachable")

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"host": "192.168.1.4"}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}


async def test_user_flow_aborts_on_duplicate(hass) -> None:
    MockConfigEntry(
        domain=DOMAIN, unique_id="0B3961F3", data={"host": "192.168.1.4"}
    ).add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"host": "192.168.1.99"}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_reconfigure_flow_updates_host(hass, bypass_entry_setup) -> None:
    entry = MockConfigEntry(
        domain=DOMAIN, unique_id="0B3961F3", data={"host": "192.168.1.4"}
    )
    entry.add_to_hass(hass)

    result = await entry.start_reconfigure_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"host": "192.168.1.55"}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert entry.data["host"] == "192.168.1.55"

    await hass.async_block_till_done()


async def test_setup_and_unload_entry(hass) -> None:
    entry = MockConfigEntry(
        domain=DOMAIN, unique_id="0B3961F3", data={"host": "192.168.1.4"}
    )
    entry.add_to_hass(hass)

    with (
        patch(
            "custom_components.yamaha_ync.client.YncClient.get_zone_capabilities",
            AsyncMock(
                return_value=ZoneCapabilities(
                    has_volume=True,
                    room_name="Main",
                    scene_names={"Scene_1": "Movie Viewing", "Scene_2": "TV Viewing"},
                )
            ),
        ),
        patch(
            "custom_components.yamaha_ync.client.YncClient.get_zone_status",
            AsyncMock(return_value=ZoneStatus(power=False)),
        ),
        patch(
            "custom_components.yamaha_ync.notify_listener.YncNotifyListener.start",
            AsyncMock(),
        ),
        patch(
            "custom_components.yamaha_ync.notify_listener.YncNotifyListener.stop",
            AsyncMock(),
        ),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        assert entry.state is ConfigEntryState.LOADED
        assert entry.runtime_data.data.device.model_name == "RX-A3080"
        assert "main" in entry.runtime_data.data.zones

        # One media_player and one remote entity for the single "main" zone
        # this fixture configures -- confirms the new `remote` platform
        # registered and set up cleanly alongside the existing ones.
        assert len(hass.states.async_entity_ids("media_player")) == 1
        remote_entity_ids = hass.states.async_entity_ids("remote")
        assert len(remote_entity_ids) == 1
        remote_state = hass.states.get(remote_entity_ids[0])
        assert remote_state.attributes["activity_list"] == [
            "Movie Viewing",
            "TV Viewing",
        ]

        assert await hass.config_entries.async_unload(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.NOT_LOADED
