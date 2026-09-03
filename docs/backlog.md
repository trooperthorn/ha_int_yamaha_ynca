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
