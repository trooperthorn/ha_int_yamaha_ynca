"""Shared test fixtures.

Nothing global here on purpose. `pytest-homeassistant-custom-component`
registers itself as an installed pytest plugin automatically once it's in
the venv (see requirements_test.txt) -- it provides the `hass` and
`enable_custom_integrations` fixtures that tests/test_ha_integration.py
uses, requested there directly rather than via an autouse fixture here.

That matters on native Windows specifically: pulling in the HA plugin's
custom asyncio event loop policy for *every* test (via an autouse fixture)
collides with `pytest-socket`'s default network block -- a Windows
ProactorEventLoop needs a real loopback socket just to construct itself,
before any test code runs. Keeping the dependency scoped to the tests that
actually need `hass` means the protocol/model/client/notify-listener suite
keeps running locally without the HA plugin ever loading for it:

    pytest tests/test_xml_protocol.py tests/test_models.py \
           tests/test_client.py tests/test_notify_listener.py -p no:homeassistant

test_ha_integration.py is written to run wherever `hass` fixtures work
normally -- CI (Linux) -- see README.md's Status section for the specifics.
"""
