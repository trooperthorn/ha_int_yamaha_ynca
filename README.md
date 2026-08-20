# Yamaha AV Receiver (YNC)

A Home Assistant custom integration for Yamaha network AV receivers, built on
Yamaha's officially-documented **YNC** protocol (`/YamahaRemoteControl/ctrl`,
HTTP/XML) rather than the community `YNCA` protocol (TCP 50000). Built and
validated against a Yamaha RX-A3080 (AVENTAGE, firmware 2.16/3.14).

This exists because the two other paths for this device both fall short:
the orphaned core `yamaha` integration and its `rxv` library only ever poll,
and the actively-maintained core `yamaha_musiccast` integration doesn't
reach AVENTAGE-specific controls like surround program or HDMI output
routing. Full writeup, protocol comparison, and rationale are in the
[project technical assessment](https://claude.ai/code/artifact/09cf7feb-3607-4cb6-bc6f-5aaf56f9be1f).

## What makes this different

Yamaha's own internal protocol spec ("Overview of YNC / YRSC") documents a
push mechanism nobody currently implements: the receiver multicasts a UPnP
`NOTIFY` packet the instant Power, Input, Volume, or Play_Info changes in
any zone. `notify_listener.py` listens for it, so state changes reach Home
Assistant immediately instead of on the next poll tick. A slow (60s)
backstop poll still runs regardless, per the spec's own recommendation that
event delivery isn't guaranteed.

## Entities

Each zone (Main, Zone 2, Zone 3, Zone 4 -- whichever `Feature_Existence`
confirms are present) is modeled as its own HA device:

| Platform | Entities |
|---|---|
| `media_player` | Power, mute, volume, source select |
| `number` | Volume (dB), subwoofer trim, dialogue lift/level, DTS dialogue control |
| `select` | YPAO volume, extra bass, adaptive DRC (Auto/On/Off) |
| `switch` | Party mode, pure direct, one per HDMI output |
| `binary_sensor` | "Needs external amplifier" (from `Volume_Existence`) |
| `sensor` | Input title, sound program, enhancer type (diagnostic) |

Sound program and enhancer type are read-only `sensor`s rather than
`select`s deliberately -- the full valid-option list for either isn't
confirmed for this model, only today's live value.

## A live finding worth flagging

Probing the real device while building this (`scripts/probe_device.py`)
turned up something the original assessment didn't have yet: **Zone 3's
current input was reported as `Main Zone Sync`** -- a selectable *input*,
distinct from `Party_Info` (which was `Off` on every zone at the time).
That means "sync this zone to Main Zone" may actually be a normal
`Input_Sel` choice per zone rather than (or in addition to) Party Mode.
Worth confirming which of the two the receiver's own remote/menu calls
"zone sync" before wiring the Zone 4 -> Monoprice routing blueprint to one
or the other -- `set_input(zone_id, "Main Zone Sync")` is already possible
with the client as built if that turns out to be the right lever.

## Status

Phase 1 (client + push listener) and Phase 2 (entities) are implemented and
validated against real hardware -- `scripts/probe_device.py` performs a
read-only round trip against a live receiver, and `tests/` covers the
protocol/model/client/notify-parsing layer using real captured payloads as
fixtures (21 tests, all passing).

**Not yet done** -- Phase 3 (quality-scale hardening) and Phase 5 (publish):

- Config-flow and coordinator tests need a full `pytest-homeassistant-custom-component`
  harness, not just the lightweight stub used for the protocol-layer tests.
- Translations exist for English only.
- `FuncTag_List` (the ~600-flag capability bitmask) isn't decoded --
  entities are gated on the specific fields they need instead.
- The UPnP push path is implemented per spec but not yet confirmed firing
  in practice on this unit's firmware; see the assessment's open items.
- Not yet submitted anywhere -- install via HACS as a custom repository
  pointing at this repo, or by copying `custom_components/yamaha_ync/`
  into your Home Assistant `config/custom_components/` directory.

## Development

```bash
python -m venv .venv
.venv/Scripts/pip install -r requirements_test.txt
.venv/Scripts/pytest tests/ -v
.venv/Scripts/python scripts/probe_device.py <receiver-ip>   # read-only, safe against real hardware
```

## Blueprints

`blueprints/automation/` has two starting points referenced in the
assessment:

- `yamaha_zone4_monoprice_handoff.yaml` -- turns on a Monoprice zone and
  selects its source when a line-out-only Yamaha zone powers on, gated
  behind an `input_boolean` so it's opt-in.
- `yamaha_severe_weather_dialogue_boost.yaml` -- raises Dialogue Level
  during a severe weather alert and restores it afterward.
