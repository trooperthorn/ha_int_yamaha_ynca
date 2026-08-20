"""Make the protocol/model layer importable and testable without a full
Home Assistant install.

`custom_components/yamaha_ync/__init__.py` (correctly, for real runtime use)
imports `homeassistant.*` at module level, which isn't installed in this
lightweight test environment. Stubbing just the two parent packages in
sys.modules -- with `__path__` pointing at the real directories -- lets
Python's submodule import machinery load `xml_protocol.py`, `models.py`, and
`client.py` directly without ever executing that top-level `__init__.py`.
Modules that genuinely need `homeassistant` (coordinator, entity, the
platform files) are exercised separately once `homeassistant` is available.
"""
from __future__ import annotations

import pathlib
import sys
import types

ROOT = pathlib.Path(__file__).resolve().parent.parent
COMPONENT_DIR = ROOT / "custom_components" / "yamaha_ync"


def _stub_package(name: str, path: pathlib.Path) -> None:
    if name in sys.modules:
        return
    module = types.ModuleType(name)
    module.__path__ = [str(path)]
    sys.modules[name] = module


_stub_package("custom_components", ROOT / "custom_components")
_stub_package("custom_components.yamaha_ync", COMPONENT_DIR)
