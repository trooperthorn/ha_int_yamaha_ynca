"""xml_protocol.py against both synthetic and real captured device responses."""
from __future__ import annotations

import pathlib

import pytest

from custom_components.yamaha_ync.xml_protocol import (
    YncProtocolError,
    build_get,
    build_put,
    dig,
    parse_response,
)

FIXTURES = pathlib.Path(__file__).parent / "fixtures"


def test_build_get_matches_spec_example() -> None:
    body = build_get(["Main_Zone", "Power_Control", "Power"])
    assert (
        '<YAMAHA_AV cmd="GET"><Main_Zone><Power_Control><Power>GetParam'
        "</Power></Power_Control></Main_Zone></YAMAHA_AV>" in body
    )


def test_build_put_matches_spec_example() -> None:
    body = build_put(["System", "Mem_Guard"], "Off")
    assert (
        '<YAMAHA_AV cmd="PUT"><System><Mem_Guard>Off</Mem_Guard></System>'
        "</YAMAHA_AV>" in body
    )


def test_parse_response_rejects_nonzero_rc() -> None:
    with pytest.raises(YncProtocolError):
        parse_response('<YAMAHA_AV rsp="PUT" RC="2"></YAMAHA_AV>')


def test_parse_response_rejects_malformed_xml() -> None:
    with pytest.raises(YncProtocolError):
        parse_response("<YAMAHA_AV rsp=\"GET\"><unterminated>")


def test_parse_response_rejects_wrong_root() -> None:
    with pytest.raises(YncProtocolError):
        parse_response('<NOT_YAMAHA_AV RC="0"></NOT_YAMAHA_AV>')


def test_parse_real_main_zone_basic_status() -> None:
    xml_text = (FIXTURES / "main_zone_basic_status.xml").read_text()
    _rc, body = parse_response(xml_text)

    assert dig(body, ["Main_Zone", "Basic_Status", "Power_Control", "Power"]) == "Standby"
    assert dig(body, ["Main_Zone", "Basic_Status", "Volume", "Lvl", "Val"]) == "-415"
    assert (
        dig(body, ["Main_Zone", "Basic_Status", "Input", "Input_Sel_Item_Info", "Title"])
        == "Great Room TV eARC"
    )
    assert (
        dig(
            body,
            [
                "Main_Zone",
                "Basic_Status",
                "Sound_Video",
                "Dialogue_Adjust",
                "Dialogue_Lift",
            ],
        )
        == "4"
    )


def test_parse_real_zone4_config_confirms_no_amplifier() -> None:
    xml_text = (FIXTURES / "zone4_config.xml").read_text()
    _rc, body = parse_response(xml_text)

    assert dig(body, ["Zone_4", "Config", "Volume_Existence"]) == "Not Exist"
    assert dig(body, ["Zone_4", "Config", "Name", "Zone"]) == "Kitchen"


def test_dig_returns_none_for_missing_path() -> None:
    assert dig({"A": {"B": "C"}}, ["A", "Z"]) is None
    assert dig({"A": {"B": "C"}}, ["A", "B", "C"]) is None
