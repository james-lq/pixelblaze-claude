"""Pixel maps: which map a pattern wants, and getting it onto the device.

A Pixelblaze holds **one** map per device, not one per pattern. Two conventions
grew up in this workspace — a project-level `pixel-map.js` and a per-pattern
`<stem>.mapper.js` — and both are kept, resolved in that precedence:

    <stem>.mapper.js   beside the pattern, wins if present
    project.toml `pixel_map`   the project's default
    neither            the project is 1D and wants no map at all

The last case is not "leave whatever is there". A project that declares no map
deploys an *empty* one, which is what stops a stale map from another project
sitting on the device and quietly bending a 1D pattern's coordinates. That is a
destructive act on the device's state, so `deploy_map=False` opts out and
`pixelblaze_get_pixel_map` saves a copy first.
"""

import logging
from pathlib import Path

import requests

from .config import Project
from .sidecar import content_hash

logger = logging.getLogger(__name__)

MAP_SUFFIX = ".mapper.js"
MAP_FILE = "pixelmap.txt"

# `getMapFunction()` in pixelblaze-client is an HTTP GET with no timeout, so a
# device that stops answering mid-request hangs the caller indefinitely. Every
# read here goes through `read_map()` instead, which is the same request with a
# deadline on it.
READ_TIMEOUT_S = 10.0


def map_for_pattern(js_path: Path, project: Project) -> tuple[Path | None, str]:
    """The map a pattern should be deployed against.

    Returns the source file (None when the project declares no map) and its
    text (empty when there is none). The empty string is meaningful: it is the
    instruction to clear the device's map, not an absence of instruction.
    """
    per_pattern = js_path.with_name(js_path.stem + MAP_SUFFIX)
    if per_pattern.exists():
        return per_pattern, per_pattern.read_text(encoding="utf-8")

    project_map = project.pixel_map_path
    if project_map is not None:
        if not project_map.exists():
            raise FileNotFoundError(
                f"{project.name}/project.toml declares pixel_map = "
                f"'{project.manifest.pixel_map}', but {project_map} does not exist."
            )
        return project_map, project_map.read_text(encoding="utf-8")

    return None, ""


def is_empty(map_text: str) -> bool:
    """Whether a map is 'no map'.

    A device whose map has been cleared through the web UI reports a single
    whitespace character rather than an empty body, so whitespace-only counts
    as empty on both sides of a comparison.
    """
    return not map_text.strip()


def map_hash(map_text: str) -> str:
    """Hash of a map's source, for the sidecar's `map_hash` and for deciding
    whether the device already has this map."""
    return content_hash(map_text)


def read_map(pb, timeout_s: float = READ_TIMEOUT_S) -> str:
    """The map function currently on the device, as text.

    This is `getMapFunction()` with a timeout: the library's version can block
    forever on an unresponsive device. Returns "" when the device has no map.
    """
    url = pb.getUrl(MAP_FILE)
    try:
        response = requests.get(url, timeout=timeout_s, proxies=getattr(pb, "proxyDict", None))
    except requests.Timeout as e:
        raise TimeoutError(
            f"Timed out after {timeout_s}s reading the pixel map from {url}. "
            "The device is reachable but not answering HTTP; it may be resetting."
        ) from e
    if response.status_code == 404:
        return ""
    response.raise_for_status()
    return response.text


def write_map(pb, map_text: str) -> None:
    """Put a map on the device, or clear it when `map_text` is empty.

    Setting a map compiles it: the JS is run against the device's pixel count to
    produce coordinates, which become the binary map data the renderer uses. So
    clearing cannot go through the same path — there is no function to run — and
    is done by writing an empty map function and empty map data directly.
    """
    if is_empty(map_text):
        pb.putFile(f"/{MAP_FILE}", "\n")
        # Without this the compiled map data would survive, and render2D would
        # keep using coordinates from a map the device no longer admits to.
        pb.setMapData(bytes(), saveToFlash=True)
        return
    pb.setMapFunction(map_text)


def sync_map(pb, js_path: Path, project: Project) -> dict:
    """Bring the device's map in line with what this pattern wants.

    Returns what happened, for the caller to report and to record in the
    sidecar. The map is only written when it actually differs, so a redeploy of
    an unchanged pattern costs one HTTP GET.
    """
    source, wanted = map_for_pattern(js_path, project)
    current = read_map(pb)

    wanted_hash = map_hash(wanted)
    result = {
        "source": str(source) if source else None,
        "map_hash": wanted_hash,
        "wanted_empty": is_empty(wanted),
    }

    if is_empty(wanted) and is_empty(current):
        result["action"] = "unchanged (no map)"
        return result
    if map_hash(current) == wanted_hash:
        result["action"] = "unchanged"
        return result

    write_map(pb, wanted)
    result["action"] = "cleared" if is_empty(wanted) else "pushed"
    result["previous_hash"] = map_hash(current)
    if is_empty(wanted):
        logger.warning(
            "Cleared the pixel map on the device: %s declares none. "
            "Use deploy_map=False to leave the device's map alone.",
            project.name,
        )
    return result
