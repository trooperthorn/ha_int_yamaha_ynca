# AGENTS.md

Guidelines for AI agents working on this repository.

## Project Overview

**Yamaha YNCA** is a custom Home Assistant integration for Yamaha AV receivers using the YNCA protocol over serial or network connections. It supports Yamaha RX-A, RX-V, AVENTAGE, TSR, and HTR receivers from 2010 onwards.

- **Language**: Python 3.14+
- **Framework**: Home Assistant Custom Component
- **Core dependency**: [`ynca`](https://github.com/mvdwetering/ynca) — the YNCA protocol library

---

## Repository Structure

```
custom_components/yamaha_ynca/   # Integration source code
  __init__.py                    # Entry setup, platform registration
  config_flow.py                 # Config wizard (serial / network)
  options_flow.py                # Options/settings UI
  const.py                       # Constants and LOGGER
  entity.py                      # Shared base entity mixin
  helpers.py                     # Utility functions (scale, version parsing)
  input_helpers.py               # ynca.Input → HA source mapping
  services.py                    # Custom HA services/actions
  diagnostics.py                 # Diagnostic data
  media_player.py                # Main media player platform
  button.py / switch.py / select.py / number.py / sensor.py / remote.py
  translations/en.json           # UI strings (entity names, etc.)

tests/                           # pytest test suite
  conftest.py                    # Fixtures: create_mock_zone, setup_integration
  mock_yncaconnection.py         # Fake YNCA connection for tests
  test_*.py                      # Per-platform and per-feature tests

docs/DEVELOPING.md               # Extended developer guide
pyproject.toml                   # Project config, dependencies, tool config
coverage.sh                      # Run pytest + mypy (CI equivalent)
bump_ynca_version.sh             # Update ynca package version everywhere
```

---

## Dev Environment Setup

Requires **Python 3.14**.

```bash
python3.14 -m venv venv
source ./venv/bin/activate
pip install -e .[dev]
```

---

## Running Tests & Checks

```bash
# Full check — same as CI (pytest + mypy)
./coverage.sh

# Tests only
pytest tests

# Type checking only
mypy custom_components --check-untyped-defs

# Format code
ruff format

# Lint with auto-fix
ruff check --fix
```

pytest is configured in `pyproject.toml`: async mode is `auto`, coverage is collected for `custom_components/yamaha_ynca`, and HTML + terminal reports are generated.

Always run `./coverage.sh` (or at minimum `pytest tests`) before considering a change complete.

**Test coverage must remain at 100%.** Every new code path requires a corresponding test. If coverage drops, add tests — do not add `# pragma: no cover` exclusions unless the code is genuinely unreachable (e.g., inside a `TYPE_CHECKING` block).

---

## Code Conventions

### Linting & Formatting

- **Ruff** handles both formatting and linting. The ruleset is `ALL` with specific ignores defined in `pyproject.toml`.
- Docstrings are intentionally omitted (D100–D107 are ignored).
- Use the import aliases configured in `pyproject.toml`:

  ```python
  import homeassistant.helpers.area_registry as ar
  import homeassistant.helpers.config_validation as cv
  import homeassistant.helpers.device_registry as dr
  import homeassistant.helpers.entity_registry as er
  import homeassistant.helpers.issue_registry as ir
  import voluptuous as vol
  ```

### Type Hints

- All code is type-annotated; mypy runs with `--check-untyped-defs`.
- Use `TYPE_CHECKING` guards for imports used only in annotations to avoid circular imports:

  ```python
  from typing import TYPE_CHECKING
  if TYPE_CHECKING:  # pragma: no cover
      from homeassistant.core import HomeAssistant
  ```

### Logging

- Import and use the shared logger from `const.py`:

  ```python
  from .const import LOGGER
  LOGGER.debug("message %s", value)
  ```

### Entity Description Pattern

All platforms define entities declaratively using `EntityDescription` dataclasses:

```python
@dataclass(frozen=True, kw_only=True)
class YncaSwitchEntityDescription(SwitchEntityDescription):
    on: Enum | None = None
    off: Enum | None = None
    function_names: list[str] | None = None
```

Add new entities by appending entries to the appropriate `ZONE_ENTITY_DESCRIPTIONS` list — do not write new entity subclasses unless genuinely necessary.

### Update Callbacks

Entities subscribe to YNCA updates using a consistent pattern:

```python
async def async_added_to_hass(self):
    self._subunit.register_update_callback(self.update_callback)

def update_callback(self, function: str, value: Any):
    if function in self._relevant_updates:
        self.schedule_update_ha_state()
```

### Feature Detection

Use walrus operators to conditionally create entities based on receiver capabilities:

```python
if zone := getattr(api, "zone2"):
    entities.append(YamahaYncaZone(zone))
```

### Async

All setup and I/O functions are `async`. Follow Home Assistant's async patterns throughout (`ConfigEntry`, `async_add_entities`, etc.).

### Home Assistant Best Practices

Follow the [Home Assistant developer documentation](https://developers.home-assistant.io/) for all integration patterns. Key points:

- Use `EntityDescription` dataclasses for entity definitions (already established in this codebase).
- Set `_attr_has_entity_name = True` and rely on translation keys for entity names — never hardcode strings.
- Use `EntityCategory.CONFIG` or `EntityCategory.DIAGNOSTIC` where appropriate.
- Register entities via `async_add_entities` from the platform setup function; do not instantiate entities outside of platform setup.
- Avoid blocking calls in the event loop; all I/O must be async or offloaded.
- Use `hass.data` only through typed `ConfigEntry.runtime_data`; do not store arbitrary data in `hass.data` with string keys.
- When in doubt, refer to how existing platforms in this integration are implemented — they are the reference.

---

## Adding an Entity (Quick Reference)

1. Ensure the `ynca` package supports the command. If a version update is needed, create a separate PR using `bump_ynca_version.sh` to update `manifest.json` and `pyproject.toml`.
2. Add an `EntityDescription` entry to the appropriate `ZONE_ENTITY_DESCRIPTIONS` list in the relevant platform file (e.g., `switch.py`).
3. Add a translation entry in `translations/en.json` under `entities/<platform>/<key>/name`.
4. Add or update tests in `tests/test_<platform>.py`.
5. Update `README.md` if the new entity/feature is user-visible.

See `docs/DEVELOPING.md` for a detailed walkthrough with a real example (PR #480).

---

## Adding an Input

1. Extend the `Mapping` list in `input_helpers.py` with the new `ynca.Input` enum value.
2. Link the subunit attribute if the input has playback state/metadata; leave the list empty for simple inputs (e.g., HDMI).
3. Update `README.md` and note in the release that users must enable the input in integration options.

---

## Tests

- Test fixtures live in `tests/conftest.py`. Use `create_mock_zone()` to get a mock zone with all attributes pre-set to `None` (preventing unintended entity creation).
- When adding attributes to a zone mock, set them to `None` in `create_mock_zone` to keep existing tests unaffected.
- For entities disabled by default, use the `entity_registry_enabled_by_default` pytest fixture.
- Asserts (`S101`) and magic values (`PLR2004`) are allowed in test files.
- The integration uses `pytest-homeassistant-custom-component` — use `MockConfigEntry` and the provided async fixtures.

---

## Markdown Style

All Markdown files in this repository must be free of [markdownlint](https://github.com/DavidAnson/markdownlint) warnings. Write clean, standards-compliant Markdown:

- Blank line required before and after headings, lists, and code blocks.
- No trailing spaces; end files with a single newline.
- No multiple consecutive blank lines.
- Ordered lists must use sequential numbering.
- Code blocks must specify a language identifier.

**One exception is allowed**: GitHub-flavoured `<details>`/`<summary>` HTML blocks in Markdown files trigger `MD033` (inline HTML) — these are permitted because GitHub renders them natively and there is no Markdown equivalent.

---

## CI / CD

Four GitHub Actions workflows:

| Workflow | Trigger | What it does |
|---|---|---|
| `validations.yaml` ("Release gates") | Push to main, PR, nightly, `workflow_call` | pytest, ruff, mypy, hassfest, HACS validation |
| `security.yaml` | Push, PR, weekly | CodeQL (Python), bandit |
| `release.yaml` | Push to main, `workflow_dispatch` | Runs `validations.yaml`, then reads the version already in `manifest.json` (via `.release.json`), tags it, builds the HACS archive, and publishes a GitHub Release with an SPDX SBOM, SHA256SUMS, and build/SBOM attestations. A no-op if that version is already published. |
| `prepare-release.yml` | `workflow_run` after `release.yaml` completes | If `main` has release-bearing changes since the last published tag, computes the next `v<YYYY.MM.DD>.<build>` version with a GitHub App token, pushes it on `automation/calver-release`, opens a PR, and auto-merges it once checks pass. That merge is what `release.yaml` then tags and publishes. |

`main` is branch-protected, so nobody bumps `manifest.json`'s version or
pushes a tag directly: `prepare-release.yml` routes the version bump through
a normal PR merge, which is what protected-branch checks actually gate.
Requires the `RELEASE_AUTOMATION_CLIENT_ID` repo variable and
`RELEASE_AUTOMATION_PRIVATE_KEY` secret for a GitHub App with Contents and
Pull requests read/write, installed on this repository. A change is
considered CI-safe if `./coverage.sh` passes cleanly.

---

## Key Files to Understand First

| File | Why |
|---|---|
| `custom_components/yamaha_ynca/__init__.py` | Integration entry point; how platforms are loaded |
| `custom_components/yamaha_ynca/entity.py` | Base class all setting entities inherit from |
| `custom_components/yamaha_ynca/media_player.py` | Largest and most complex platform |
| `tests/conftest.py` | All shared fixtures; read before writing any test |
| `docs/DEVELOPING.md` | Full developer guide including release process |
