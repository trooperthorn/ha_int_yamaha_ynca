# Protocol and device facts

Wire-format and device-specific behavior that the code depends on but that
isn't obvious from reading the code alone.

## AUDIO input reporting

The following receiver models do not report the (single) AUDIO input
properly: RX-V475, RX-V575, HTR-4066, HTR-5066 (these four share firmware),
and RX-V473, RX-V573, HTR-4065, HTR-5065 (these four share a different
firmware). `helpers.receiver_requires_audio_input_workaround()` checks the
model name against this list so `__init__.py` can apply the AUDIO-naming
workaround only where it's needed.

| Model group | Models | Verified |
| --- | --- | --- |
| RX-V475 firmware family | RX-V475, RX-V575, HTR-4066, HTR-5066 | Verified — reported at [mvdwetering/yamaha_ynca#230](https://github.com/mvdwetering/yamaha_ynca/issues/230) |
| RX-V473 firmware family | RX-V473, RX-V573, HTR-4065, HTR-5065 | Verified — reported at [mvdwetering/yamaha_ynca#234](https://github.com/mvdwetering/yamaha_ynca/discussions/234) |

## 2CHDECODER / ProLogic II variants

For the `2CHDECODER` YNCA function, several ProLogic II variants map to the
same functionality on a receiver, but the variant names differ by receiver
generation:

- Older receivers report `DolbyPl2xyyy` variants, which get mapped to
  `DolbyPl2yyy` when no presence speakers are available.
- Newer receivers report `DolbyProLogicII_yyy` variants instead of
  `DolbyPl2yyy`.

`select.py`'s `SURROUNDDECODEROPTIONS_PROLOGIC_II_MAPPING` and
`PROLOGIC_II_TO_NEW_PROTOCOL_MAPPING` normalize both generations to a single
`DolbyPl2yyy` set so the UI can show one consistent "ProLogic II" option and
send the correct value back to the receiver.

Unverified: the `DolbyPl2xyyy` variants currently can't be set from the UI
(only received); fixing that is deferred until someone needs it.
