"""Pattern preview thumbnails, generated the same way the Pixelblaze web UI does.

The web UI builds a pattern's thumbnail by streaming preview frames from the
running pattern, painting one frame per row into a canvas 150 rows tall,
gamma-correcting each channel, shrinking the result to 100 columns, and
encoding a JPEG whose quality is lowered in steps until it fits in ~5 KB.
The pattern list then shows the image one row at a time (each row is one
frame), scrolled by CSS, which is what makes thumbnails look animated.

A pattern saved without a thumbnail makes the pattern-list page stall for
ten seconds and pop the "Pixelblaze is having trouble loading preview
images" dialog, so every save should carry one.
"""

import io
import json
import logging
import time

from PIL import Image

logger = logging.getLogger(__name__)

PREVIEW_WIDTH = 100      # columns in the stored thumbnail
PREVIEW_FRAMES = 150     # rows (one per frame) in the stored thumbnail
TARGET_SIZE = 5120       # bytes; the UI lowers JPEG quality until under this
QUALITY_START = 90
QUALITY_MIN = 50
QUALITY_STEP = 5
GAMMA = 1 / 2.2          # the UI's display gamma for preview pixels

_PREVIEW_FRAME_TYPE = 5  # binary websocket frame type for preview frames
_GAMMA_TABLE = bytes(round(255 * (v / 255) ** GAMMA) for v in range(256))


def capture_preview(pb, frames: int = PREVIEW_FRAMES, timeout_s: float = 30.0) -> bytes:
    """Stream preview frames from the pattern currently running on `pb` and
    return a thumbnail JPEG built the way the web UI builds one.

    The caller must make sure the pattern to capture is the active one. At the
    device's preview rate (~25 fps) 150 frames take about six seconds.

    Raises TimeoutError if the device stops sending frames.
    """
    ws = pb.ws
    old_timeout = ws.gettimeout()
    rows: list[bytes] = []
    ws.send(json.dumps({"sendUpdates": True}))
    try:
        ws.settimeout(5)
        deadline = time.monotonic() + timeout_s
        while len(rows) < frames:
            if time.monotonic() > deadline:
                raise TimeoutError(
                    f"Preview capture timed out after {len(rows)}/{frames} frames"
                )
            frame = ws.recv()
            if isinstance(frame, bytes):
                if frame and frame[0] == _PREVIEW_FRAME_TYPE:
                    pixels = frame[1:]
                    n = len(pixels) // 3
                    if n:
                        rows.append(pixels[: n * 3].translate(_GAMMA_TABLE))
            elif isinstance(frame, str):
                # Keep the client library's caches coherent for unsolicited frames.
                if frame.startswith('{"fps":'):
                    pb.latestStats = frame
                elif frame.startswith('{"activeProgram":'):
                    pb.latestSequencer = frame
    finally:
        ws.send(json.dumps({"sendUpdates": False}))
        ws.settimeout(old_timeout)
    return encode_preview(rows)


def encode_preview(rows: list[bytes]) -> bytes:
    """Turn a list of gamma-corrected RGB rows (one per frame) into the
    100x150 thumbnail JPEG the pattern list expects."""
    width = len(rows[0]) // 3
    stride = width * 3
    raw = b"".join(r[:stride].ljust(stride, b"\0") for r in rows)
    img = Image.frombytes("RGB", (width, len(rows)), raw)
    img = img.resize((PREVIEW_WIDTH, PREVIEW_FRAMES), Image.LANCZOS)
    return _to_jpeg(img)


def placeholder_preview() -> bytes:
    """A neutral dim grey dashed chase, used when a live capture is not
    possible. Reads as "no preview yet" in the pattern list."""
    img = Image.new("RGB", (PREVIEW_WIDTH, PREVIEW_FRAMES), (0, 0, 0))
    px = img.load()
    for y in range(PREVIEW_FRAMES):
        for x in range(PREVIEW_WIDTH):
            if ((x + y) // 5) % 2 == 0:
                px[x, y] = (70, 70, 70)
    return _to_jpeg(img)


def _to_jpeg(img: Image.Image) -> bytes:
    quality = QUALITY_START
    while True:
        buf = io.BytesIO()
        img.save(buf, "JPEG", quality=quality)
        data = buf.getvalue()
        if len(data) <= TARGET_SIZE or quality - QUALITY_STEP < QUALITY_MIN:
            return data
        quality -= QUALITY_STEP
