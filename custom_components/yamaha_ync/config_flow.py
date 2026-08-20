"""Config flow: user-entered host, SSDP discovery, and IP reconfiguration."""
from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.service_info.ssdp import SsdpServiceInfo

from .client import YncClient, YncConnectionError
from .const import DOMAIN

STEP_USER_SCHEMA = vol.Schema({vol.Required(CONF_HOST): str})


class YamahaYncConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle setup, SSDP discovery, and reconfiguration for one receiver."""

    VERSION = 1

    def __init__(self) -> None:
        self._discovered_host: str | None = None
        self._discovered_name: str | None = None

    async def _async_probe(self, host: str) -> tuple[str, str] | None:
        """Return (system_id, model_name) if `host` answers as a YNC device."""
        session = async_get_clientsession(self.hass)
        client = YncClient(host, session)
        try:
            device = await client.get_device_info()
        except YncConnectionError:
            return None
        if not device.system_id:
            return None
        return device.system_id, device.model_name

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            host = user_input[CONF_HOST]
            probed = await self._async_probe(host)
            if probed is None:
                errors["base"] = "cannot_connect"
            else:
                system_id, model_name = probed
                await self.async_set_unique_id(system_id)
                self._abort_if_unique_id_configured(updates={CONF_HOST: host})
                return self.async_create_entry(
                    title=model_name, data={CONF_HOST: host}
                )

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_SCHEMA, errors=errors
        )

    async def async_step_ssdp(
        self, discovery_info: SsdpServiceInfo
    ) -> ConfigFlowResult:
        host = discovery_info.ssdp_headers.get("_host") or (
            discovery_info.ssdp_location.split("/")[2].split(":")[0]
            if discovery_info.ssdp_location
            else None
        )
        if host is None:
            return self.async_abort(reason="cannot_connect")

        probed = await self._async_probe(host)
        if probed is None:
            # Plenty of non-Yamaha devices answer the generic MediaRenderer
            # SSDP type declared in manifest.json -- silently bow out rather
            # than showing the user a form for a device that isn't ours.
            return self.async_abort(reason="not_yamaha_ync_device")

        system_id, model_name = probed
        await self.async_set_unique_id(system_id)
        self._abort_if_unique_id_configured(updates={CONF_HOST: host})

        self._discovered_host = host
        self._discovered_name = model_name
        self.context["title_placeholders"] = {"name": model_name}
        return await self.async_step_confirm()

    async def async_step_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if user_input is not None:
            return self.async_create_entry(
                title=self._discovered_name or "Yamaha AV Receiver",
                data={CONF_HOST: self._discovered_host},
            )
        return self.async_show_form(
            step_id="confirm",
            description_placeholders={"name": self._discovered_name or ""},
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            host = user_input[CONF_HOST]
            probed = await self._async_probe(host)
            if probed is None:
                errors["base"] = "cannot_connect"
            else:
                system_id, _model_name = probed
                # Set this flow's unique_id from what the new host actually
                # reports *before* comparing -- otherwise the mismatch check
                # is comparing against nothing and aborts every time.
                await self.async_set_unique_id(system_id)
                # Refuse to silently repoint this config entry at a
                # different physical receiver.
                self._abort_if_unique_id_mismatch()
                return self.async_update_reload_and_abort(
                    self._get_reconfigure_entry(), data={CONF_HOST: host}
                )

        current_entry = self._get_reconfigure_entry()
        return self.async_show_form(
            step_id="reconfigure",
            data_schema=vol.Schema(
                {vol.Required(CONF_HOST, default=current_entry.data[CONF_HOST]): str}
            ),
            errors=errors,
        )
