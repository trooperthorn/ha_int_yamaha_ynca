"""Typed views over the YAMAHA_AV response trees.

Field coverage here is deliberately scoped to what has been confirmed live
against a Yamaha RX-A3080 (firmware 2.16/3.14) rather than the full function
tree Yamaha ships across its receiver lineup -- the `FuncTag_List` capability
bitmask on System/Service is the source of truth for what any *other* model
supports, and isn't decoded here yet (see the project README).
"""
from __future__ import annotations

from dataclasses import dataclass, field

from .xml_protocol import dig


def _val(node: object) -> str | None:
    return node if isinstance(node, str) and node != "" else None


def _int(node: object) -> int | None:
    v = _val(node)
    try:
        return int(v) if v is not None else None
    except ValueError:
        return None


def _bool_on_off(node: object) -> bool | None:
    v = _val(node)
    if v is None:
        return None
    return v == "On"


@dataclass
class DeviceInfo:
    """System/Config, identifying the physical unit."""

    model_name: str
    system_id: str
    version: str
    zones: list[str]
    input_names: dict[str, str] = field(default_factory=dict)

    @classmethod
    def from_response(cls, body: dict) -> DeviceInfo:
        config = dig(body, ["System", "Config"]) or {}
        feature_existence = config.get("Feature_Existence", {}) or {}
        zones = [
            zone
            for zone, node in (
                ("main", "Main_Zone"),
                ("zone2", "Zone_2"),
                ("zone3", "Zone_3"),
                ("zone4", "Zone_4"),
            )
            if feature_existence.get(node) == "1"
        ]
        input_names = dig(body, ["System", "Config", "Name", "Input"]) or {}
        return cls(
            model_name=config.get("Model_Name", "Yamaha AV Receiver"),
            system_id=config.get("System_ID", ""),
            version=config.get("Version", ""),
            zones=zones,
            input_names={k: v for k, v in input_names.items() if isinstance(v, str)},
        )


@dataclass
class ZoneCapabilities:
    """Zone_N/Config -- what this zone can do, decided once at setup."""

    has_volume: bool
    room_name: str | None = None
    scene_names: dict[str, str] = field(default_factory=dict)

    @classmethod
    def from_response(cls, body: dict) -> ZoneCapabilities:
        volume_existence = dig(body, ["Config", "Volume_Existence"])
        room_name = dig(body, ["Config", "Name", "Zone"])
        scenes = dig(body, ["Config", "Name", "Scene"]) or {}
        return cls(
            has_volume=volume_existence != "Not Exist",
            room_name=_val(room_name),
            scene_names={k: v for k, v in scenes.items() if isinstance(v, str) and v},
        )


@dataclass
class ZoneStatus:
    """Zone_N/Basic_Status -- everything that changes during normal use."""

    power: bool | None = None
    sleep: str | None = None
    volume_db: float | None = None
    mute: bool | None = None
    subwoofer_trim_db: float | None = None
    balance: int | None = None
    input_id: str | None = None
    input_title: str | None = None
    sound_program: str | None = None
    enhancer_type: str | None = None
    party_mode: bool | None = None
    pure_direct: bool | None = None
    tone_bass_db: float | None = None
    tone_treble_db: float | None = None
    hdmi_outputs: dict[str, bool] = field(default_factory=dict)
    ypao_volume: str | None = None
    extra_bass: str | None = None
    adaptive_drc: str | None = None
    dialogue_lift: int | None = None
    dialogue_level: int | None = None
    dts_dialogue_control: int | None = None

    @classmethod
    def from_response(cls, body: dict) -> ZoneStatus:
        status = body.get("Basic_Status", body)

        power_control = status.get("Power_Control", {}) or {}
        volume = status.get("Volume", {}) or {}
        vol_lvl = volume.get("Lvl", {}) or {}
        input_node = status.get("Input", {}) or {}
        input_info = input_node.get("Input_Sel_Item_Info", {}) or {}
        surround = status.get("Surround", {}) or {}
        program_current = dig(surround, ["Program_Sel", "Current"]) or {}
        sound_video = status.get("Sound_Video", {}) or {}
        tone = sound_video.get("Tone", {}) or {}
        tone_manual = tone.get("Manual", tone) or {}
        bass = tone_manual.get("Bass", {}) or {}
        treble = tone_manual.get("Treble", {}) or {}
        hdmi_out = dig(sound_video, ["HDMI", "Output"]) or {}
        dialogue = sound_video.get("Dialogue_Adjust", {}) or {}

        raw_power = _val(power_control.get("Power"))
        return cls(
            power=(raw_power == "On") if raw_power is not None else None,
            sleep=_val(power_control.get("Sleep")),
            volume_db=_scaled(vol_lvl),
            mute=_bool_on_off(volume.get("Mute")),
            subwoofer_trim_db=_scaled(volume.get("Subwoofer_Trim", {})),
            balance=_int(volume.get("Balance")),
            input_id=_val(input_node.get("Input_Sel")),
            input_title=_val(input_info.get("Title")),
            sound_program=_val(program_current.get("Sound_Program")),
            enhancer_type=_val(surround.get("Enhancer_Type")),
            party_mode=_bool_on_off(status.get("Party_Info")),
            pure_direct=_bool_on_off(dig(sound_video, ["Pure_Direct", "Mode"])),
            tone_bass_db=_scaled(bass),
            tone_treble_db=_scaled(treble),
            hdmi_outputs={
                k: v == "On"
                for k, v in hdmi_out.items()
                if isinstance(v, str) and not k.endswith("_Info")
            },
            ypao_volume=_val(sound_video.get("YPAO_Volume")),
            extra_bass=_val(sound_video.get("Extra_Bass")),
            adaptive_drc=_val(sound_video.get("Adaptive_DRC")),
            dialogue_lift=_int(dialogue.get("Dialogue_Lift")),
            dialogue_level=_int(dialogue.get("Dialogue_Lvl")),
            dts_dialogue_control=_int(dialogue.get("DTS_Dialogue_Control")),
        )


@dataclass
class NetUsbPlayInfo:
    """<node>/Play_Info for a network/USB media source (NET_RADIO, Spotify,
    SERVER, Bluetooth, AirPlay, and the other services in
    const.NETUSB_FAMILY_INPUTS).

    Confirmed live for NET_RADIO, Spotify, SERVER, Bluetooth, and AirPlay --
    each uses a slightly different subset of Meta_Info field names (radio
    has Station/Song, Spotify has Artist/Track, others have Artist/Song),
    normalized here into one shape.
    """

    playback_state: str | None = None  # "Play" / "Pause" / "Stop"
    title: str | None = None
    artist: str | None = None
    album: str | None = None
    station: str | None = None
    elapsed_seconds: int | None = None
    total_seconds: int | None = None
    shuffle: bool | None = None
    repeat: str | None = None  # "Off" / "One" / "All"
    album_art_url: str | None = None
    device_name: str | None = None  # Bluetooth's paired device, when connected

    @classmethod
    def from_response(cls, body: dict) -> NetUsbPlayInfo:
        info = body.get("Play_Info", body)
        meta = info.get("Meta_Info", {}) or {}
        time_node = info.get("Time", {}) or {}
        play_mode = info.get("Play_Mode", {}) or {}
        album_art = info.get("Album_ART", {}) or {}

        return cls(
            playback_state=_val(info.get("Playback_Info")),
            title=_val(meta.get("Song")) or _val(meta.get("Track")),
            artist=_val(meta.get("Artist")),
            album=_val(meta.get("Album")),
            station=_val(meta.get("Station")),
            elapsed_seconds=_int(time_node.get("Elapsed")),
            total_seconds=_int(time_node.get("Total")),
            shuffle=_bool_on_off(play_mode.get("Shuffle")),
            repeat=_val(play_mode.get("Repeat")),
            album_art_url=_val(album_art.get("URL")),
            device_name=_val(info.get("Device_Name")),
        )


def _scaled(lvl_node: dict) -> float | None:
    """Yamaha expresses fractional values as Val / 10^Exp (e.g. dB levels)."""
    if not isinstance(lvl_node, dict):
        return None
    val = _int(lvl_node.get("Val"))
    if val is None:
        return None
    exp = _int(lvl_node.get("Exp")) or 0
    return val / (10**exp)
