# Decisions

Dated decisions with the alternative rejected and why.

## 2026-09-03: Keep custom_components/__init__.py

An earlier pass removed `custom_components/__init__.py`, on the assumption
it was a leftover test-harness artifact (the file the scanner in
`~/.claude/skills/ha-dev-current` flags as `hacs-stray-file`). That broke
`mypy custom_components --check-untyped-defs`: without an `__init__.py`
making `custom_components` an actual package, mypy resolves files under it
inconsistently against the package the repo's own editable install exposes,
and fails with "Source file found twice under different module names:
yamaha_ynca.const and custom_components.yamaha_ynca.const" for every file.
Restoring the empty `__init__.py` fixes it (verified: `mypy` goes from
failing on the first file to `Success: no issues found in 18 source files`).

This file does not violate HACS's structural rule, which is specifically
"there must only be one integration per repository, i.e. only one
subdirectory to custom_components/" (hacs-documentation
`source/docs/publish/integration.md`); a loose file directly under
`custom_components/` is not a second subdirectory, and it isn't part of
the archive `scripts/build_release_artifacts.py` zips (only
`custom_components/yamaha_ynca/` is), so it never reaches a HACS install.
Kept, with this note, rather than removed a second time.

## 2026-09-04: Leave upstream code comments in place

The comment-to-docs pass that the other trooperthorn repositories went through
was not applied to files this fork inherits from `mvdwetering/yamaha_ynca`
(`migrations.py` and the platform modules carry the only candidates, five
history-style notes in the migration steps). Rewriting upstream comments
would turn every future upstream merge into a conflict for no runtime gain.
The pass applies only to files this fork owns: the workflows, the release
scripts, and `docs/`.

