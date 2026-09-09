"""Finding PixelBlazes on the local network by their UDP discovery beacons.

Every PixelBlaze with discovery enabled broadcasts a beacon on port 1889 every
second or so: three little-endian uint32s — a packet type of 42, the sender's
chip ID, and the sender's clock. The chip ID in that beacon is the same value
`getConfig` reports, so a beacon alone identifies a device; this module still
only collects addresses, and the caller connects to read the full config.

`pixelblaze-client` ships a `PixelblazeEnumerator` for this, but it is not
usable here: its listener thread blocks in `recvfrom()` with no timeout, so
`stop()` joins a thread that will not return until another beacon happens to
arrive. This is the same job with a socket timeout and no thread.
"""

import logging
import socket
import struct
import time

logger = logging.getLogger(__name__)

BEACON_PORT = 1889
BEACON_PACKET = 42
_BEACON_FORMAT = "<LLL"  # packet type, sender id, sender clock
_BEACON_SIZE = struct.calcsize(_BEACON_FORMAT)

# Beacons arrive about once a second per device, so a few seconds is enough to
# hear from everything awake on the network.
DEFAULT_LISTEN_S = 4.0


def listen_for_beacons(duration_s: float = DEFAULT_LISTEN_S) -> dict[str, int]:
    """Listen for beacons and return `{host: chip_id_int}` for each device heard.

    Returns an empty dict rather than raising if the port cannot be bound —
    another process listening on 1889 is a plausible local condition, and the
    caller can still fall back to the registry's known hosts.
    """
    found: dict[str, int] = {}
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind(("0.0.0.0", BEACON_PORT))
    except OSError as e:
        logger.warning("Could not listen for PixelBlaze beacons on port %d: %s", BEACON_PORT, e)
        return found

    deadline = time.monotonic() + duration_s
    try:
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                break
            sock.settimeout(remaining)
            try:
                data, addr = sock.recvfrom(1024)
            except socket.timeout:
                break
            except OSError as e:
                logger.warning("Beacon listen failed: %s", e)
                break
            if len(data) < _BEACON_SIZE:
                continue
            packet_type, sender_id, _clock = struct.unpack(_BEACON_FORMAT, data[:_BEACON_SIZE])
            if packet_type == BEACON_PACKET:
                found[addr[0]] = sender_id
    finally:
        sock.close()
    return found
