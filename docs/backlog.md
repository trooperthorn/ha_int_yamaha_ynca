# Backlog

Dated, open items that don't belong as TODO comments in code.

## 2026-09-03: Strengthen entity-description assertions in number/switch tests

`tests/test_number.py` (`test_async_setup_entry_adds_number_and_number_initialvolume_entities`)
and `tests/test_switch.py` (its switch-entities equivalent) assert that
entities were created with `assert_has_calls(... ANY ...)`, checking only
that a call happened for the right subunit, not that the expected
`EntityDescription` (translation key, category, etc.) was actually used.
Improve these to assert on the specific entity description passed, not just
the call count and subunit.

## 2026-09-03: `register_update_callback.call_args` is fragile where a mock subunit has multiple registrants

`test_mediaplayer_entity_source_rename` grabbed
`mock_ynca.sys.register_update_callback.call_args.args[0]` to get "the"
callback registered on the mocked `sys` subunit, but more than one entity
type registers a callback there (the media player's own `update_sys_callback`
and the "all zones power" switch's `update_callback`), and platform setup
order isn't deterministic. `.call_args` returns whichever was registered
last, so the test intermittently grabbed the wrong one and asserted against
state that could never change. Fixed by filtering `call_args_list` for the
callback whose bound `__self__.entity_id` matches the entity under test.

At least ten other tests use the same `<mock>.register_update_callback.call_args.args[0]`
pattern against `mock_zone`/`mock_zone_main`/`netradio`/`tidal`/`usb` mocks
(test_button.py, test_entity.py, test_media_player.py, test_remote.py,
test_switch.py). None are currently known to be flaky, but any of them could
have the same latent bug if a second entity type ever registers on the same
mocked subunit. Worth an audit and the same entity_id-filtering fix applied
proactively rather than waiting for each to flake.

## 2026-09-04: Merge the three upstream `dev` commits

`upstream/dev` is three commits ahead of `main` (the last is "Bump ynca version
to 6.2.1 (#556)", already matched here by PR 5). Merge `upstream/dev` deliberately
rather than syncing, because this fork carries the release baseline that upstream
does not have.

