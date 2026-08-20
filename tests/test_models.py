"""models.py against real captured device responses."""
from __future__ import annotations

import pathlib

from custom_components.yamaha_ync.models import (
    DeviceInfo,
    NetUsbPlayInfo,
    ZoneCapabilities,
    ZoneStatus,
)
from custom_components.yamaha_ync.xml_protocol import parse_response

FIXTURES = pathlib.Path(__file__).parent / "fixtures"


def _load(name: str) -> dict:
    _rc, body = parse_response((FIXTURES / name).read_text())
    return body


def test_zone_status_from_main_zone_basic_status() -> None:
    body = _load("main_zone_basic_status.xml")["Main_Zone"]
    status = ZoneStatus.from_response(body)

    assert status.power is False  # "Standby"
    assert status.volume_db == -41.5  # Val=-415, Exp=1 -> -415/10
    assert status.mute is False
    assert status.subwoofer_trim_db == -6.0
    assert status.input_id == "AUDIO3"
    assert status.input_title == "Great Room TV eARC"
    assert status.sound_program == "Surround Decoder"
    assert status.enhancer_type == "High Resolution"
    assert status.party_mode is False
    assert status.pure_direct is False
    assert status.tone_bass_db == -6.0
    assert status.tone_treble_db == 2.0
    assert status.hdmi_outputs == {"OUT_1": True, "OUT_2": True}
    assert status.ypao_volume == "Auto"
    assert status.extra_bass == "Auto"
    assert status.adaptive_drc == "Auto"
    assert status.dialogue_lift == 4
    assert status.dialogue_level == 3
    assert status.dts_dialogue_control == 6


def test_zone_status_from_zone4_has_no_volume_fields() -> None:
    body = _load("zone4_basic_status.xml")["Zone_4"]
    status = ZoneStatus.from_response(body)

    assert status.power is False
    assert status.volume_db is None
    assert status.input_id == "AV4"
    assert status.party_mode is False
    assert status.hdmi_outputs == {"OUT_3": False}


def test_zone_capabilities_confirms_zone4_has_no_amplifier() -> None:
    body = _load("zone4_config.xml")["Zone_4"]
    capabilities = ZoneCapabilities.from_response(body)

    assert capabilities.has_volume is False
    assert capabilities.room_name == "Kitchen"


def test_zone_capabilities_parses_real_scene_names() -> None:
    body = _load("main_zone_config_scenes.xml")["Main_Zone"]
    capabilities = ZoneCapabilities.from_response(body)

    assert capabilities.room_name == "Main"
    assert capabilities.scene_names == {
        "Scene_1": "Movie Viewing",
        "Scene_2": "Radio Listening",
        "Scene_3": "Music Listening",
        "Scene_4": "NET Audio Listening",
        "Scene_5": "STB Viewing",
        "Scene_6": "Game Playing",
        "Scene_7": "TV Viewing",
        "Scene_8": "Media Server Listening",
    }


def test_netusb_play_info_from_real_idle_spotify() -> None:
    body = _load("spotify_play_info.xml")["Spotify"]
    info = NetUsbPlayInfo.from_response(body)

    assert info.playback_state == "Stop"
    assert info.title is None
    assert info.artist is None
    assert info.shuffle is True
    assert info.repeat == "All"


def test_netusb_play_info_from_populated_airplay() -> None:
    # The AirPlay/Play_Info *structure* below is confirmed live against the
    # real receiver, but nothing was actually playing during capture
    # (Playback_Info was "Pause" with every Meta_Info/Time field empty) --
    # the values here are hand-filled into that same confirmed shape to
    # exercise parsing of a populated response.
    body = _load("airplay_play_info_playing.xml")["AirPlay"]
    info = NetUsbPlayInfo.from_response(body)

    assert info.playback_state == "Play"
    assert info.title == "Deacon Blues"
    assert info.artist == "Steely Dan"
    assert info.album == "Aja"
    assert info.elapsed_seconds == 87
    assert info.total_seconds == 214
    assert info.album_art_url == "http://192.168.1.4/AlbumART/1"


def test_device_info_from_system_config() -> None:
    body = {
        "System": {
            "Config": {
                "Model_Name": "RX-A3080",
                "System_ID": "0B3961F3",
                "Version": "2.16/3.14",
                "Feature_Existence": {
                    "Main_Zone": "1",
                    "Zone_2": "1",
                    "Zone_3": "1",
                    "Zone_4": "1",
                    "Tuner": "1",
                },
                "Name": {"Input": {"AUDIO_3": "Great Room TV eARC"}},
            }
        }
    }
    device = DeviceInfo.from_response(body)

    assert device.model_name == "RX-A3080"
    assert device.system_id == "0B3961F3"
    assert device.zones == ["main", "zone2", "zone3", "zone4"]
    assert device.input_names == {"AUDIO_3": "Great Room TV eARC"}
