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
| `media_player` | Power, mute, volume (+ step up/down), source select, play/pause/stop/next/previous, shuffle, repeat, title/artist/album/duration/position/artwork -- the last block only while the zone is on a netusb-family source (NET_RADIO, Spotify, SERVER, Bluetooth, AirPlay, and siblings; see below) |
| `remote` | One per zone. Scenes (`Config/Name/Scene` -- e.g. "Movie Viewing", "TV Viewing") exposed as `RemoteEntityFeature.ACTIVITY`; `send_command` also accepts input names and `play`/`pause`/`stop`/`next`/`previous` |
| `number` | Volume (dB), subwoofer trim, dialogue lift/level, DTS dialogue control |
| `select` | YPAO volume, extra bass, adaptive DRC (Auto/On/Off) |
| `switch` | Party mode, pure direct, one per HDMI output |
| `binary_sensor` | "Needs external amplifier" (from `Volume_Existence`) |
| `sensor` | Input title, sound program, enhancer type (diagnostic) |

Sound program and enhancer type are read-only `sensor`s rather than
`select`s deliberately -- the full valid-option list for either isn't
confirmed for this model (two guesses at the paths that would enumerate it,
`Program_Sel/Config` and `Program_Sel/Avail`, both came back HTTP 400 --
genuinely invalid on this model, not just non-leaf). `media_player`'s
`select_sound_mode` is the same story and stays unsupported for the same
reason -- a `select`/sound-mode list with guessed options would either
reject valid choices or silently accept invalid ones.

**netusb-family playback** (`media_player` transport controls, `remote`'s
`play`/`pause`/etc. commands): `Play_Info` for a network source lives at its
*own* top-level XML node (`<Spotify>`, `<NET_RADIO>`, `<SERVER>`, etc.), not
nested under the zone's `Basic_Status` -- confirmed live for NET_RADIO,
Spotify, SERVER, Bluetooth, and AirPlay (Napster/TIDAL/Deezer/Amazon_Music/
Qobuz/SiriusXM/Pandora/USB/JUKE are included on the same `Feature_Existence`
key-naming pattern, not individually probed). The transport command values
themselves (`Play`/`Stop`/`Pause`/`Skip Fwd`/`Skip Rev`) are the
community-documented (`rxv`/`pyamaha`) convention, not yet confirmed against
this unit's `Play_Control` container -- confirmed real as a container (a
`GetParam` on it returns RC=2, "valid node, not leaf-gettable", the same
signature every other known-real write-only container gives), just not that
exact command vocabulary. A wrong value surfaces as a normal RC-based error,
not a silent no-op. Shuffle/repeat's *set* paths, by contrast, are fully
GET-confirmed (`Play_Control/Play_Mode/Shuffle` and `.../Repeat` both
round-tripped live against Spotify's actual current values).

**Tuner** (`Tuner/Play_Info`, `Tuner/Config`) was probed and returns a full
band/frequency/preset/signal structure with real FM/AM step sizes, but isn't
wired into any entity yet -- it's a different shape than the netusb-family
sources and didn't fit this pass's scope.

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
read-only round trip against a live receiver.

Phase 3 (quality-scale hardening) and Phase 4 (blueprints/device triggers)
are substantially in: `device_trigger.py` (zone powered on/off, input
changed), `diagnostics.py`, `icons.json`, and a self-assessed
`quality_scale.yaml` are all in place, alongside `PARALLEL_UPDATES = 0` on
every platform (the client already serializes requests through its own
lock). `tests/` has 28 passing tests covering the protocol/model/client/
notify-parsing layer against real captured payloads (including the
netusb-family Play_Info shapes for Spotify/AirPlay and the real scene-name
config), runnable anywhere:

```bash
pytest tests/test_xml_protocol.py tests/test_models.py tests/test_client.py tests/test_notify_listener.py -p no:homeassistant
```

`tests/test_ha_integration.py` covers config-flow (user/error/duplicate/
reconfigure) and setup/unload (now asserting the `remote` platform and its
activity list too) against a real `hass` fixture -- 5 more tests, **33
total**, all green on `.github/workflows/test.yml` (`ubuntu-latest`).
It can't run locally on native Windows: `pytest-homeassistant-custom-component`'s
event loop policy needs a real loopback socket to even construct itself,
which collides with `pytest-socket`'s default network block (a
well-documented Windows/asyncio ProactorEventLoop quirk, not something
specific to this integration). CI is what actually verified this file --
and it earned its keep: it caught a real reconfigure-flow bug (comparing a
still-unset unique_id) along with four CI/test-plumbing issues (pip cache
path, a missing test dependency, faked-setup teardown crashing on unset
`runtime_data`, and a `pycares` DNS-resolver thread lazily spun up by a real
`aiohttp.ClientSession` the harness's thread-leak check has no opt-out
for) before landing green.

**Still open:**

- Platform entity behavior (media_player, remote, number, select, switch)
  isn't covered by tests yet beyond confirming the entities register and
  read the right activity list -- only config-flow/setup, the protocol
  layer, and models.py's parsing of every response shape are covered.
- `Play_Control/Playback`'s exact command vocabulary isn't confirmed
  against this unit (see the netusb-family note above).
- `BROWSE_MEDIA` isn't implemented -- `SERVER/List_Info` (confirmed live)
  has the menu/cursor structure for it, but full list navigation is a
  meaningfully bigger scope than this pass covered.
- Tuner isn't wired into any entity yet, despite being fully probed.
- Translations exist for English only.
- `FuncTag_List` (the ~600-flag capability bitmask) isn't decoded --
  entities are gated on the specific fields they need instead.
- The UPnP push path is implemented per spec but not yet confirmed firing
  in practice on this unit's firmware; see the assessment's open items.
- Not registered in `home-assistant/brands` yet (Bronze `brands` rule).
- Not yet published anywhere -- install via HACS as a custom repository
  pointing at this branch, or by copying `custom_components/yamaha_ync/`
  into your Home Assistant `config/custom_components/` directory.

## Development

```bash
python -m venv .venv
.venv/Scripts/pip install -r requirements_test.txt
.venv/Scripts/pytest tests/ -v          # full suite; needs Linux for test_ha_integration.py
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
