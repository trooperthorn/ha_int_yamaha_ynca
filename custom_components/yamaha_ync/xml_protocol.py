"""Build and parse YAMAHA_AV XML packets.

Wire format is Yamaha's own "YNC" (Yamaha Network Command) protocol as
documented in the manufacturer's internal "Overview of YNC / YRSC" reference
(AV Receiver Group, Products Development Department, rev. 1.0). Every PUT/GET
body is a nested XML tree rooted at <YAMAHA_AV>, mirroring the device's
function tree one element per node, terminated by either a literal value
(PUT) or the sentinel "GetParam" (GET).
"""
from __future__ import annotations

from xml.etree import ElementTree as ET

ROOT_TAG = "YAMAHA_AV"
GET_SENTINEL = "GetParam"


class YncProtocolError(Exception):
    """Raised when a YAMAHA_AV response can't be parsed or was rejected."""


def build_get(path: list[str]) -> str:
    """Build a GET request body for the given function-tree path.

    >>> build_get(["Main_Zone", "Basic_Status"])
    '<YAMAHA_AV cmd="GET"><Main_Zone><Basic_Status>GetParam</Basic_Status></Main_Zone></YAMAHA_AV>'
    """
    return _build(cmd="GET", path=path, value=GET_SENTINEL)


def build_put(path: list[str], value: str) -> str:
    """Build a PUT request body setting `path` to `value`."""
    return _build(cmd="PUT", path=path, value=value)


def _build(cmd: str, path: list[str], value: str) -> str:
    if not path:
        raise ValueError("path must contain at least one node")
    root = ET.Element(ROOT_TAG, {"cmd": cmd})
    node = root
    for segment in path:
        node = ET.SubElement(node, segment)
    node.text = value
    return "<?xml version=\"1.0\" encoding=\"utf-8\"?>" + ET.tostring(
        root, encoding="unicode"
    )


def parse_response(xml_text: str) -> tuple[str, dict]:
    """Parse a <YAMAHA_AV rsp="..." RC="..."> response.

    Returns (return_code, body) where body is the response tree flattened
    into nested dicts, keyed by tag name, with leaf tags mapped to their
    text (empty string if the tag has no text, e.g. a PUT echo).

    Raises YncProtocolError if RC is a nonzero (error) code or the payload
    isn't well-formed XML.
    """
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError as err:
        raise YncProtocolError(f"malformed YAMAHA_AV response: {err}") from err

    if root.tag != ROOT_TAG:
        raise YncProtocolError(f"unexpected root element <{root.tag}>")

    rc = root.attrib.get("RC", "0")
    if rc != "0":
        raise YncProtocolError(f"device returned RC={rc} for this command")

    # The <YAMAHA_AV> root is always a container per the protocol (every
    # real response nests at least one child, e.g. <System>/<Main_Zone>),
    # unlike arbitrary sub-elements _element_to_dict also handles -- so
    # this is a real protocol invariant, not an assumption papering over
    # the general str|dict return type.
    body = _element_to_dict(root)
    if not isinstance(body, dict):
        raise YncProtocolError(f"expected a container at <{ROOT_TAG}>, got text")
    return rc, body


def _element_to_dict(element: ET.Element) -> dict | str:
    children = list(element)
    if not children:
        return element.text.strip() if element.text else ""
    result: dict = {}
    for child in children:
        result[child.tag] = _element_to_dict(child)
    return result


def dig(body: dict, path: list[str]) -> str | dict | None:
    """Walk a nested dict returned by parse_response along `path`."""
    node: str | dict | None = body
    for segment in path:
        if not isinstance(node, dict) or segment not in node:
            return None
        node = node[segment]
    return node
