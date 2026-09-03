# Developing

This document describes some useful info when developing for the `yamaha_ynca` integration.

## Table of contents

- [Dev environment](#dev-environment)
- [Release](#release)
- [Update ynca package](#update-ynca-package)
- [Add an entity](#add-an-entity)
- [Add an input](#add-an-input)

## Dev environment

The integration has no specific build/package tool requirements other than a standard virtual env. It should work with any editor, but I only used it with VS Code.

These are the commands to setup a dev environment and run the tests after the repo has been cloned.

```bash
# Create a virtual env
$ python3.13 -m venv venv
# Activate the virtual env
$ source ./venv/bin/activate
# Install dev dependencies
(venv) $ pip install -e .[dev]
# Run all tests with coverage and run mypy
(venv) $ ./coverage.sh
```

Other commands

```bash
(venv) $ pytest tests
(venv) $ ruff format
```

## Release

Releases are automatic. `main` is branch-protected, so nobody bumps
`manifest.json`'s version or pushes a tag by hand; a normal PR merge is the
only path onto `main`, release-bearing or not.

Two workflows cooperate:

- `.github/workflows/prepare-release.yml` runs after every successful
  `Release` run. If `main` has release-bearing changes since the last
  published tag, it uses a GitHub App token (not the default `GITHUB_TOKEN`,
  which can't push past branch protection) to compute the next
  `v<YYYY.MM.DD>.<build>` version, push it on `automation/calver-release`,
  open a PR, and auto-merge it once the required checks pass.
- `.github/workflows/release.yaml` runs on every push to `main`, including
  that auto-merge. It waits for the same gates that guard pull requests
  (pytest, ruff, mypy, hassfest, HACS validation), reads the version already
  in `manifest.json` (via `.release.json`), tags it, builds the HACS
  archive, and publishes a GitHub Release with an SPDX SBOM, a
  `SHA256SUMS` checksum file, and build/SBOM attestations (verify with
  `gh attestation verify`). It's a no-op if that version is already
  published, which is what happens on an ordinary code-only merge before
  `prepare-release.yml` has had a chance to bump the version.

Cleaning up the auto-generated release notes on [the releases page](https://github.com/trooperthorn/ha_int_yamaha_ynca/releases)
afterward, and adding a breaking-changes section when one applies, is still
a manual step.

`release.py` predates this automation and is no longer part of the release
path; it's kept only until it's confirmed safe to remove.

## Update ynca package

To update to a new version of the ynca package simply run the `bump_ynca_version.sh` script and it will update the required references.

## Using the debug server

The `ynca` package has a debug server that can be used instead of a real receiver. It can be used to emulate basic request/response commands. See the documentation in the ynca repository for more info.

## Add an entity

Adding an entity is usually easy when it follows the common patterns.

As an example lets add the Extra Bass switch as done in [PR #480](https://github.com/mvdwetering/yamaha_ynca/pull/480).

First the `ynca` needs to support the command. For info on how to add it there see <https://github.com/mvdwetering/ynca/tree/master/docs>. Next make sure to update the `ynca` version used by the integration contains that command. Use the `bump_ynca_version.sh` script to update the version in all the required places (during development you can also install the ynca package in the venv). Bumping dependencies like the ynca version is usually done in a separate PR.

Next the related entity platform should be extended. In this case we will be adding a switch, so `switch.py` is the file to edit. Other entity platforms can be updated similarly.

To add the new command switch it is enough to just add a new [entity description](https://developers.home-assistant.io/docs/core/entity/#entity-description) entry to the ZONE_ENTITY_DESCRIPTIONS list like below.

```python
    YncaSwitchEntityDescription(
        key="exbass",
        entity_category=EntityCategory.CONFIG,
        on=ynca.ExBass.AUTO,
        off=ynca.ExBass.OFF,
    ),
```

The `key` field is the attribute name in the ynca package, it is also used as translation key.
More info about `entity_category` can be found [here in the Home Assistant developer documentation](https://developers.home-assistant.io/docs/core/entity/).
The `on` and `off` fields are the enum values to be used when turning the switch on/off.

Check out the documentation of `YncaSwitchEntityDescription` for more details.

That is the code part done. With this info the `YncaSwitchEntity` implementation will take care of handling incoming commands to update the switch and call the `ynca` package with the correct data when the switch changes in Home Assistant.

Now update the translations by adding a section matching the `key` under `entities/switch` similar to the others. This will make sure the switch gets a proper name.

```json
      "exbass": {
        "name": "Extra Bass"
      },
```

Only thing left to do now is add/extend tests. Since this command is very straight forward, just fix the test by updating the amount of switch entities that is created during setup.

A few notes on tests:

- If new attributes were added to a zone in the ynca package make sure to set them to `None` in `create_mock_zone`. It avoids entities being created when not intended.
- If a new entity is disabled by default use the `entity_registry_enabled_by_default` fixture to enable them for the test

If something new was added list it in the README

And thats is all that is needed.
(I would still recommend to do a quick manual test against a real receiver or the `debug_server`)

## Add an input

This assumes the `ynca.Input` enum is already extended and the ynca package has a version with the new input (and new subunit if relevant).

To make the input available in Home Assistant the mapping in `input_helpers.py` needs to be extended like below.

```python
    Mapping(ynca.Input.NETRADIO, ["netradio"]),
    Mapping(ynca.Input.HDMI4, []),
```

If the new input is related to a subunit the subunit attribute of the ynca package should be listed. It will be used by the `media_player` entity to figure out where to look for things playback state and metadata. For other inputs like HDMI4 in the example the list stays empty.

To wrap up:

- Add/extend tests if needed.
- Update README with the new inputs
- In the release notes mention that users will need to enable the new inputs in the integration options.
