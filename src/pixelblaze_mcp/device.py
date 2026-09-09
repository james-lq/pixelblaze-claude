"""Connecting to a Pixelblaze, and proving it is the one that was asked for.

A registry entry is keyed by the device's immutable chip ID, but reached by
`host`, which DHCP can reassign. So every connection to a registered device
checks that the box answering at that address reports the expected chip ID and
refuses to go any further if it does not. That is the guard against deploying
onto the wrong controller after an address reshuffle.

The check costs one `getConfigSettings()` call (~0.1 s) and its result is cached
for the life of the MCP process, so it happens once per device per session.
"""

import logging
from contextlib import contextmanager
from typing import Any

from pixelblaze import Pixelblaze

from .config import Device, format_chip_id, is_offline, resolve_device

logger = logging.getLogger(__name__)

OFFLINE_MSG = (
    "PixelBlaze offline mode is active — no connection to the device will be made. "
    "To go online, call pixelblaze_set_offline_mode(enabled=False). "
    "Documentation tools (docs_get_api_reference, docs_get_mapper_reference) "
    "and local pattern file tools remain available."
)

# host -> chip ID confirmed during this process. Only ever holds hosts whose
# identity has been checked and matched.
_verified: dict[str, str] = {}

# Names that turned out to differ from the registry, so the warning is logged
# once per host rather than on every call.
_name_warned: set[str] = set()


def read_config(pb: Pixelblaze) -> dict[str, Any]:
    """The device's settings, plus its expander config folded in.

    `getConfigSettings()` already caches whatever expander packet arrived, so
    the config is read from that. Never call `getConfigExpander()`: when a
    device reports no expander packet it spins forever, because its retry loop
    waits on a field that `getConfigSettings()` gave up on filling.
    """
    settings = pb.getConfigSettings()
    expander = pb.latestExpander
    if isinstance(expander, dict):
        settings = {**settings, "expanders": expander.get("expanders", [])}
    return settings


def _expander_channels(config: dict[str, Any]) -> int:
    """Expander channels actually driving pixels.

    An expander board reports all eight of its channels whether or not they are
    wired up; the unused ones carry `count: 0`, so only non-empty channels are
    counted.
    """
    total = 0
    for exp in config.get("expanders", []):
        rows = exp.get("rows", {})
        for entries in (rows.values() if isinstance(rows, dict) else []):
            for entry in entries if isinstance(entries, list) else [entries]:
                if isinstance(entry, dict) and entry.get("count"):
                    total += 1
    return total


def describe(config: dict[str, Any]) -> dict[str, Any]:
    """The live facts worth showing next to a registry entry."""
    return {
        "chip_id": format_chip_id(config["chipId"]),
        "name": config.get("name"),
        "board": config.get("boardType"),
        "firmware": config.get("ver"),
        "pixel_count": config.get("pixelCount"),
        "led_type": config.get("ledType"),
        "color_order": config.get("colorOrder"),
        "expander_channels": _expander_channels(config),
    }


def _verify(pb: Pixelblaze, device: Device) -> None:
    """Confirm the box at `device.host` is the one the registry says it is.

    A chip ID mismatch is fatal. A display name mismatch is only a warning:
    the name is a human hint that changes in the web UI in two seconds, and
    the tooling never matches on it.
    """
    if device.ad_hoc or device.chip_id is None:
        return  # an ad-hoc host was asked for by address; there is nothing to check against
    if _verified.get(device.host) == device.chip_id:
        return

    config = read_config(pb)
    actual = format_chip_id(config["chipId"])
    if actual != device.chip_id:
        raise RuntimeError(
            f"Refusing to continue: the device at {device.host} is not the one in the registry.\n"
            f"  devices.toml expects: {device.chip_id}"
            f"{f' ({device.name})' if device.name else ''}\n"
            f"  the device reports:   {actual} ({config.get('name')!r})\n"
            "The address has probably been reassigned by DHCP. Run "
            "pixelblaze_list_devices(check=True) or pixelblaze_discover_devices to fix the host."
        )

    live_name = config.get("name")
    if live_name and device.name and live_name != device.name and device.host not in _name_warned:
        _name_warned.add(device.host)
        logger.warning(
            "Device %s is named %r on the device but %r in devices.toml. Matching is by chip ID, "
            "so this is cosmetic; pixelblaze_list_devices(check=True) refreshes it.",
            device.chip_id,
            live_name,
            device.name,
        )

    _verified[device.host] = device.chip_id


@contextmanager
def connect(device: str | None = None, **resolve_kwargs):
    """Yield a connected, identity-checked Pixelblaze for `device`.

    `device` is resolved through the registry (chip ID, display name, host, or
    an ad-hoc address) and its identity verified before anything is yielded.
    """
    if is_offline():
        raise RuntimeError(OFFLINE_MSG)
    resolved = resolve_device(device, **resolve_kwargs)
    pb = Pixelblaze(resolved.host)
    try:
        _verify(pb, resolved)
        yield pb
    finally:
        pb._close()


@contextmanager
def connect_resolved(device: Device):
    """Like `connect`, but for a Device that has already been resolved."""
    if is_offline():
        raise RuntimeError(OFFLINE_MSG)
    pb = Pixelblaze(device.host)
    try:
        _verify(pb, device)
        yield pb
    finally:
        pb._close()
