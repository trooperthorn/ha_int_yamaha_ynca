"""_parse_notify_datagram against the spec's own worked example, plus noise."""
from __future__ import annotations

from custom_components.yamaha_ync.notify_listener import _parse_notify_datagram

SPEC_EXAMPLE_NOTIFY = (
    b"NOTIFY * HTTP/1.1\r\n"
    b"Host: 239.255.255.250:1900\r\n"
    b"NT: urn:yamaha-com:service:YamahaRemoteControl:2\r\n"
    b"NTS: yamaha:propchange\r\n"
    b"USN: uuid:4c1b8691-e9f4-0000-0000-000000000000::"
    b"urn:yamaha-com:service:YamahaRemoteControl:2\r\n"
    b"\r\n"
    b'<?xml version="1.0" encoding="utf-8"?>'
    b'<YAMAHA_AV cmd="EVENT"><Main_Zone><Property>Power</Property>'
    b"</Main_Zone></YAMAHA_AV>"
)

ZONE2_NOTIFY = (
    b"NOTIFY * HTTP/1.1\r\n"
    b"Host: 239.255.255.250:1900\r\n"
    b"NT: urn:yamaha-com:service:YamahaRemoteControl:2\r\n"
    b"NTS: yamaha:propchange\r\n"
    b"\r\n"
    b'<YAMAHA_AV cmd="EVENT"><Zone_2><Property>Power</Property>'
    b"</Zone_2></YAMAHA_AV>"
)


def test_parses_spec_example_notify() -> None:
    event = _parse_notify_datagram(SPEC_EXAMPLE_NOTIFY)
    assert event is not None
    assert event.zone_id == "main"
    assert event.property_name == "Power"


def test_parses_zone2_notify() -> None:
    event = _parse_notify_datagram(ZONE2_NOTIFY)
    assert event is not None
    assert event.zone_id == "zone2"


def test_ignores_non_yamaha_ssdp_alive_notify() -> None:
    generic_ssdp = (
        b"NOTIFY * HTTP/1.1\r\n"
        b"Host: 239.255.255.250:1900\r\n"
        b"NT: upnp:rootdevice\r\n"
        b"NTS: ssdp:alive\r\n"
        b"\r\n"
    )
    assert _parse_notify_datagram(generic_ssdp) is None


def test_ignores_msearch_response() -> None:
    msearch = b"M-SEARCH * HTTP/1.1\r\nHost: 239.255.255.250:1900\r\n\r\n"
    assert _parse_notify_datagram(msearch) is None


def test_ignores_malformed_body() -> None:
    broken = (
        b"NOTIFY * HTTP/1.1\r\n"
        b"NT: urn:yamaha-com:service:YamahaRemoteControl:2\r\n"
        b"NTS: yamaha:propchange\r\n"
        b"\r\n"
        b"<not well formed"
    )
    assert _parse_notify_datagram(broken) is None


def test_ignores_garbage_bytes() -> None:
    assert _parse_notify_datagram(b"\xff\xfe\x00\x01not http at all") is None
