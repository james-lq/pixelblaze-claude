"""MCP tools for interacting with the PixelBlaze device."""

import logging
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pixelblaze import Pixelblaze

from .config import PATTERNS_DIR, PIXELBLAZE_HOST, is_offline, set_offline
from .pattern_file import (
    find_local_pattern_file,
    new_pattern_file_path,
    parse_pattern_file,
    stamp_file,
    update_local_code,
)

logger = logging.getLogger(__name__)

_OFFLINE_MSG = (
    "PixelBlaze offline mode is active — no connection to the device will be made. "
    "To go online, call pixelblaze_set_offline_mode(enabled=False). "
    "Documentation tools (docs_get_api_reference, docs_get_mapper_reference) "
    "and local pattern file tools remain available."
)


def _now_utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


@contextmanager
def _pb():
    """Context manager that yields a connected Pixelblaze instance."""
    if is_offline():
        raise RuntimeError(_OFFLINE_MSG)
    pb = Pixelblaze(PIXELBLAZE_HOST)
    try:
        yield pb
    finally:
        pb._close()


def pixelblaze_set_offline_mode(enabled: bool) -> str:
    """Enable or disable PixelBlaze offline mode.

    When enabled, all device tools are disabled and will not attempt to connect
    to the hardware. Documentation tools and local pattern file operations remain
    available. Use this when the PixelBlaze device is not reachable.

    Phrases like "go offline", "toggle pb offline", "enable offline mode", or
    "go online" should all map to this tool.

    Args:
        enabled: True to enable offline mode, False to go back online.
    """
    set_offline(enabled)
    if enabled:
        return (
            "PixelBlaze offline mode enabled. Device tools are disabled. "
            "You can still use docs_get_api_reference and docs_get_mapper_reference. "
            "Patterns created with pixelblaze_create_pattern will be saved locally "
            "in patterns/ and can be deployed later with pixelblaze_deploy_local_pattern."
        )
    return (
        f"PixelBlaze offline mode disabled. Device tools will connect to {PIXELBLAZE_HOST} on next use."
    )


def pixelblaze_list_local_patterns() -> list[dict[str, Any]]:
    """List all PixelBlaze pattern JS files in the local patterns/ directory.

    Returns deploy status for each file: whether it has been deployed, when it
    was last deployed, and whether the local file has been modified since the
    last deploy. Useful for identifying patterns that need to be deployed or
    re-deployed to the device.
    """
    if not PATTERNS_DIR.exists():
        return []
    results = []
    for path in sorted(PATTERNS_DIR.glob("*.js")):
        try:
            info = parse_pattern_file(path)
            results.append({
                "file": path.name,
                "name": info["name"],
                "pattern_id": info["pattern_id"] or "(none)",
                "deployed_at": info["deployed_at"] or "(never)",
                "modified_since_deployed": info["modified_since_deployed"],
            })
        except Exception as e:
            results.append({"file": path.name, "error": str(e)})
    return results


def pixelblaze_deploy_local_pattern(file_path: str) -> dict[str, str]:
    """Deploy a locally saved pattern JS file to the PixelBlaze device.

    Reads code from the file, creates or updates the pattern on the device,
    then stamps the file with the deployment timestamp and hash. Use this to
    deploy patterns created or edited in offline mode.

    Args:
        file_path: Path to the pattern JS file (absolute, or relative to
            the project root).
    """
    path = Path(file_path)
    if not path.is_absolute():
        # Resolve relative paths from the project root (parent of patterns/)
        path = PATTERNS_DIR.parent / path
    if not path.exists():
        raise FileNotFoundError(f"Pattern file not found: {file_path}")

    info = parse_pattern_file(path)
    code = info["code"]
    name = info["name"]
    existing_id = info["pattern_id"]

    with _pb() as pb:
        if existing_id and existing_id != "(pending)":
            patterns = pb.getPatternList()
            name = patterns.get(existing_id, name)
            pb.savePattern(previewImage=b"", sourceCode=code, name=name, id=existing_id, allowCache=True)
            pattern_id = existing_id
        else:
            pattern_id = pb.savePattern(previewImage=b"", sourceCode=code, name=name, allowCache=True)
            pb.setActivePattern(pattern_id)

    stamp_file(path, code, pattern_id, _now_utc())
    return {"id": pattern_id, "name": name, "file": path.name}


def pixelblaze_list_patterns() -> list[dict[str, str]]:
    """List all patterns stored on the PixelBlaze device.

    Returns a list of dicts with 'id' and 'name' keys.
    """
    with _pb() as pb:
        patterns = pb.getPatternList()
        return [{"id": pid, "name": name} for pid, name in patterns.items()]


def pixelblaze_get_active_pattern() -> dict[str, str]:
    """Get the currently active (running) pattern on the PixelBlaze.

    Returns a dict with 'id' and 'name' of the active pattern.
    """
    with _pb() as pb:
        active = pb.getActivePattern()
        if active is None:
            return {"id": "", "name": "(none)"}
        # getActivePattern returns a dict like {id: name}
        pid, name = next(iter(active.items()))
        return {"id": pid, "name": name}


def pixelblaze_set_active_pattern(pattern_id: str) -> str:
    """Switch the PixelBlaze to run a specific pattern by its ID.

    Args:
        pattern_id: The pattern ID to activate (from pixelblaze_list_patterns).

    Returns a confirmation message.
    """
    with _pb() as pb:
        pb.setActivePattern(pattern_id)
        return f"Activated pattern {pattern_id}"


def pixelblaze_get_pattern_code(pattern_id: str) -> str:
    """Get the JavaScript source code of a pattern.

    Args:
        pattern_id: The pattern ID to retrieve code for.

    Returns the JavaScript source code string.
    """
    if is_offline():
        local = find_local_pattern_file(pattern_id)
        if local:
            return parse_pattern_file(local)["code"]
        raise RuntimeError(
            f"{_OFFLINE_MSG}\n\n"
            f"No local file found for pattern ID '{pattern_id}'. "
            "Check the patterns/ directory — the Pattern ID appears in the first comment "
            "line of each JS file. You can also read the file directly."
        )
    with _pb() as pb:
        code = pb.getPatternSourceCode(pattern_id)
        if code is None:
            return f"No source code found for pattern {pattern_id}"
        return code


def pixelblaze_create_pattern(name: str, code: str) -> dict[str, str]:
    """Create a new pattern on the PixelBlaze with the given JavaScript code,
    then activate it. Also saves the code to a local JS file in patterns/.

    In offline mode, saves the pattern locally as a pending file without
    deploying to the device. Use pixelblaze_deploy_local_pattern to deploy later.

    Args:
        name: Display name for the new pattern.
        code: PixelBlaze JavaScript source code (must define a render(index) function).

    Returns a dict with the new pattern's 'id' and 'name'.
    """
    if is_offline():
        path = new_pattern_file_path(name)
        stamp_file(path, code, "(pending)", None)
        return {
            "id": "(pending)",
            "name": name,
            "status": "offline — not deployed",
            "file": str(path),
            "message": (
                f"Offline mode: pattern saved to {path.name} but not deployed to the device. "
                f"Call pixelblaze_deploy_local_pattern('{path}') when the device is reachable."
            ),
        }

    with _pb() as pb:
        pattern_id = pb.savePattern(previewImage=b"", sourceCode=code, name=name, allowCache=True)
        pb.setActivePattern(pattern_id)

    path = find_local_pattern_file(pattern_id) or new_pattern_file_path(name)
    stamp_file(path, code, pattern_id, _now_utc())
    return {"id": pattern_id, "name": name, "file": path.name}


def pixelblaze_update_pattern(pattern_id: str, code: str) -> str:
    """Replace the JavaScript source code of an existing pattern.
    Also updates the local pattern JS file in patterns/ if one exists for this ID.

    In offline mode, updates the local file only — the device is not contacted.
    The local file will be marked as modified-since-deployed so it shows up in
    pixelblaze_list_local_patterns as needing re-deployment.

    Args:
        pattern_id: The ID of the pattern to update.
        code: New PixelBlaze JavaScript source code.

    Returns a confirmation message.
    """
    local_path = find_local_pattern_file(pattern_id)

    if is_offline():
        if local_path is None:
            raise RuntimeError(
                f"{_OFFLINE_MSG}\n\n"
                f"No local file found for pattern ID '{pattern_id}'. "
                "Cannot update without either a device connection or a local copy. "
                "Check patterns/ for JS files — the Pattern ID is in the first comment line."
            )
        update_local_code(local_path, code)
        return (
            f"Offline mode: updated local file {local_path.name} with new code. "
            "The device has not been updated. "
            f"Call pixelblaze_deploy_local_pattern('{local_path}') to deploy when online."
        )

    with _pb() as pb:
        patterns = pb.getPatternList()
        name = patterns.get(pattern_id, pattern_id)
        pb.savePattern(previewImage=b"", sourceCode=code, name=name, id=pattern_id, allowCache=True)

    if local_path is None:
        local_path = new_pattern_file_path(name)
    stamp_file(local_path, code, pattern_id, _now_utc())
    return f"Updated pattern '{name}' ({pattern_id}) — stamped {local_path.name}"


def pixelblaze_delete_pattern(pattern_id: str) -> str:
    """Delete a pattern from the PixelBlaze device.

    Args:
        pattern_id: The ID of the pattern to delete.

    Returns a confirmation message.
    """
    with _pb() as pb:
        pb.deletePattern(pattern_id)
        return f"Deleted pattern {pattern_id}"


def pixelblaze_get_controls() -> list[dict[str, Any]]:
    """Get the UI controls for the currently active pattern.

    Returns a list of control dicts, each with 'name', 'value', and 'type' keys.
    The controls correspond to exported slider/toggle/picker variables in the pattern code.
    """
    with _pb() as pb:
        active = pb.getActivePattern()
        if not active:
            return []
        pattern_id = next(iter(active.keys()))
        controls = pb.getPatternControls(pattern_id)
        if not controls:
            return []
        return [{"name": k, "value": v} for k, v in controls.items()]


def pixelblaze_set_control(name: str, value: float) -> str:
    """Set the value of a UI control (slider, toggle, etc.) on the active pattern.

    Args:
        name: The control variable name (as it appears in pixelblaze_get_controls).
        value: Numeric value (sliders: 0.0–1.0; toggles: 0 or 1).

    Returns a confirmation message.
    """
    with _pb() as pb:
        pb.setControl(name, value)
        return f"Set control '{name}' to {value}"


def pixelblaze_get_device_info() -> dict[str, Any]:
    """Get hardware and runtime information about the PixelBlaze device.

    Returns a dict with keys: host, pixel_count, fps, uptime_s,
    version_major, version_minor.
    """
    with _pb() as pb:
        stats = pb.getStatistics()
        info: dict[str, Any] = {
            "host": PIXELBLAZE_HOST,
            "fps": pb.getFPS(),
            "uptime_s": pb.getUptime(),
            "version_major": pb.getVersionMajor(),
            "version_minor": pb.getVersionMinor(),
        }
        if stats:
            info["pixel_count"] = stats.get("pixelCount")
            info["render_ms"] = stats.get("renderMs")
        return info


def pixelblaze_set_brightness(value: float) -> str:
    """Set the global brightness of the PixelBlaze.

    Args:
        value: Brightness level from 0.0 (off) to 1.0 (full brightness).

    Returns a confirmation message.
    """
    value = max(0.0, min(1.0, value))
    with _pb() as pb:
        pb.setBrightnessSlider(value)
        return f"Set brightness to {value:.2f}"
