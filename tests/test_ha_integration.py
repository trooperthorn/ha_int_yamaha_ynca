"""Config-flow, setup/unload, and coordinator behavior against a real `hass`.

Requires the `hass` fixture from `pytest-homeassistant-custom-component`,
which needs a working asyncio event loop of the kind pytest-socket blocks
on native Windows (see tests/conftest.py). Written and reviewed carefully
but not executable in this dev environment -- CI (.github/workflows/test.yml,
runs on ubuntu-latest) is the actual pass/fail signal for this file.
"""
from __future__ import annotations

from unittest.mock import AsyncMock, patch

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
def mock_get_device_info():
    with patch(
        "custom_components.yamaha_ync.client.YncClient.get_device_info",
        AsyncMock(return_value=FAKE_DEVICE),
    ) as mocked:
        yield mocked


async def test_user_flow_creates_entry(hass) -> None:
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


async def test_reconfigure_flow_updates_host(hass) -> None:
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


async def test_setup_and_unload_entry(hass) -> None:
    entry = MockConfigEntry(
        domain=DOMAIN, unique_id="0B3961F3", data={"host": "192.168.1.4"}
    )
    entry.add_to_hass(hass)

    with (
        patch(
            "custom_components.yamaha_ync.client.YncClient.get_zone_capabilities",
            AsyncMock(return_value=ZoneCapabilities(has_volume=True, room_name="Main")),
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

        assert await hass.config_entries.async_unload(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.NOT_LOADED
