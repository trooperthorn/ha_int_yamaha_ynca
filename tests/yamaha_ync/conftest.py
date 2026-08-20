"""Test fixtures scoped to the yamaha_ync integration.

Nothing global needed here -- this subdirectory sits under the repo's
existing tests/conftest.py, whose autouse `auto_enable_custom_integrations`
fixture already covers everything below (including this integration).

The protocol/model/client/notify-listener suite here doesn't touch
`homeassistant` at all and runs anywhere, including native Windows:

    pytest tests/yamaha_ync/test_xml_protocol.py tests/yamaha_ync/test_models.py \
           tests/yamaha_ync/test_client.py tests/yamaha_ync/test_notify_listener.py \
           -p no:homeassistant

test_ha_integration.py needs the `hass` fixture and, on native Windows,
runs into a `pytest-homeassistant-custom-component` / `pytest-socket`
interaction where the harness's asyncio event loop policy needs a real
loopback socket just to construct itself. This repo's own CI
(.github/workflows/validations.yaml) is where that file is actually
verified.
"""
