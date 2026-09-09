"""MCP tools for interacting with PixelBlaze devices.

Every tool that touches hardware takes a `device`: a chip ID from `devices.toml`,
a device's display name, or a bare IP address for a one-off. Tools that work on
local files take a `project` (a folder name under `projects/`) or a `file_path`,
which implies its project.

When `device` is omitted, it is resolved from the pattern's `.sidecar.toml`:
the device it last went to, else the project's most recently used one. So a
redeploy needs no argument, and naming a device explicitly is how a pattern
moves to a new one.
"""

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pixelblaze import Pixelblaze

from .config import (
    Project,
    is_offline,
    list_projects,
    load_project,
    project_for_path,
    resolve_device,
    resolve_path,
)
from .device import OFFLINE_MSG, connect, connect_resolved, describe, read_config
from .preview import capture_preview as capture_preview_image
from .preview import placeholder_preview
from . import sidecar as sidecar_mod
from .pattern_file import (
    canonical_pattern_name,
    device_pattern_name,
    ensure_header,
    find_local_pattern_file,
    new_pattern_file_path,
    parse_pattern_file,
    write_pattern_file,
)

logger = logging.getLogger(__name__)


def _now_utc() -> datetime:
    """Deploy timestamps are whole seconds, UTC — TOML stores them natively."""
    return datetime.now(timezone.utc).replace(microsecond=0)


def _read_controls(pb) -> dict[str, Any]:
    """The live control values for the running pattern, for the sidecar record.

    Read back rather than pushed, so tuning done in the web UI since the last
    deploy is captured instead of clobbered.
    """
    try:
        return dict(pb.getActiveControls() or {})
    except Exception as e:  # a missing control map must never fail a deploy
        logger.warning("Could not read control values back: %s", e)
        return {}


def _record_deploy(
    path: Path, code: str, pattern_id: str, device, controls: dict[str, Any] | None = None
) -> None:
    """Write the pattern file and its sidecar entry for a completed deploy."""
    sc = sidecar_mod.load(path)
    sc.record(
        device_id=device.chip_id,
        device_name=device.name,
        pattern_id=pattern_id,
        deployed_hash=sidecar_mod.content_hash(code),
        deployed_at=_now_utc(),
        controls=controls,
    )
    sc.save()


def _wants_preview(project: Project | None, override: bool | None) -> bool:
    """Whether to capture a live thumbnail: per-call argument wins, else the
    project manifest's `preview_capture`, else on."""
    if override is not None:
        return override
    return project.preview_capture if project else True


def _unwrap_source(raw: Any) -> str:
    """getPatternSourceCode() returns a JSON string '{"main": "<js>"}'; return the JS."""
    if isinstance(raw, (bytes, bytearray)):
        raw = raw.decode("utf-8")
    if isinstance(raw, str):
        try:
            parsed = json.loads(raw)
        except ValueError:
            return raw
    else:
        parsed = raw
    return parsed.get("main", raw) if isinstance(parsed, dict) else raw


def _save_pattern(
    pb: Pixelblaze,
    *,
    code: str,
    name: str,
    pattern_id: str | None = None,
    activate: bool = False,
    capture: bool = True,
) -> str:
    """Save a pattern (new when pattern_id is None) with a proper thumbnail.

    Steps:
      1. Save the code with a placeholder thumbnail so the pattern list never
         stalls on a missing preview image.
      2. Make sure the new code is actually running. Saving over the active
         pattern's ID does not restart it, so it is re-activated explicitly.
      3. Capture a live thumbnail from the running pattern, the way the web UI
         does, and re-save with it. If the pattern was not the active one it is
         activated just for the capture and the previous pattern is restored.

    Returns the pattern ID.
    """
    previously_active = pb.getActivePattern()
    is_new = pattern_id is None
    if is_new:
        pattern_id = pb.makeId()
    pb.savePattern(
        previewImage=placeholder_preview(), sourceCode=code, name=name, id=pattern_id, allowCache=True
    )
    running = previously_active
    if activate or is_new or previously_active == pattern_id:
        pb.setActivePattern(pattern_id)
        running = pattern_id

    if not capture:
        return pattern_id

    if running != pattern_id:
        pb.setActivePattern(pattern_id)
    try:
        preview = capture_preview_image(pb)
    except Exception as e:  # keep the placeholder rather than fail the save
        logger.warning("Preview capture failed for %s; keeping placeholder: %s", pattern_id, e)
        preview = None
    if preview:
        pb.savePattern(previewImage=preview, sourceCode=code, name=name, id=pattern_id, allowCache=True)
    if running != pattern_id and previously_active:
        pb.setActivePattern(previously_active)
    return pattern_id


# --- Offline mode ---------------------------------------------------------


def pixelblaze_set_offline_mode(enabled: bool) -> str:
    """Enable or disable PixelBlaze offline mode.

    When enabled, all device tools are disabled and will not attempt to connect
    to the hardware. Documentation tools and local pattern file operations remain
    available. Use this when no PixelBlaze device is reachable.

    Phrases like "go offline", "toggle pb offline", "enable offline mode", or
    "go online" should all map to this tool.

    Args:
        enabled: True to enable offline mode, False to go back online.
    """
    from .config import set_offline

    set_offline(enabled)
    if enabled:
        return (
            "PixelBlaze offline mode enabled. Device tools are disabled. "
            "You can still use docs_get_api_reference and docs_get_mapper_reference. "
            "Patterns created with pixelblaze_create_pattern will be saved locally "
            "and can be deployed later with pixelblaze_deploy_local_pattern."
        )
    return "PixelBlaze offline mode disabled. Device tools will connect on next use."


# --- Devices --------------------------------------------------------------


def pixelblaze_list_devices(check: bool = False) -> dict[str, Any]:
    """List the PixelBlaze devices registered in devices.toml.

    Each entry is keyed by the device's immutable hardware chip ID, written as
    `0x` plus 8 upper-case hex digits.

    Args:
        check: Connect to each device and report its live chip ID, name, board,
            firmware, pixel count and expander channels alongside the registry
            values. Flags any chip ID mismatch, and refreshes the stored `name`
            and `host` in devices.toml when they have drifted. Without this,
            the file is only read, never written.

    Returns a dict with the registered devices and, when check=True, what each
    one actually reported.
    """
    from .config import load_devices

    registry = load_devices()
    entries: list[dict[str, Any]] = []
    for chip_id, dev in registry.devices.items():
        entry: dict[str, Any] = {"chip_id": chip_id, "name": dev.name, "host": dev.host}
        if dev.notes:
            entry["notes"] = dev.notes
        entries.append(entry)

    if not check:
        return {"file": str(registry.path), "devices": entries}

    changed = False
    for entry in entries:
        dev = registry.devices[entry["chip_id"]]
        try:
            with connect_resolved(dev) as pb:
                live = describe(read_config(pb))
        except Exception as e:
            entry["status"] = "unreachable"
            entry["error"] = str(e)
            continue
        entry["status"] = "ok"
        entry["live"] = live
        # The chip ID cannot have drifted — connect_resolved refuses on mismatch —
        # but name and host are hints, and hints go stale.
        if live["name"] and live["name"] != dev.name:
            entry["name_was"] = dev.name
            entry["name"] = live["name"]
        if registry.set_fields(entry["chip_id"], name=live["name"], host=dev.host):
            changed = True

    if changed:
        registry.save()
    return {"file": str(registry.path), "devices": entries, "registry_updated": changed}


def pixelblaze_discover_devices(dry_run: bool = False) -> dict[str, Any]:
    """Find PixelBlaze devices on the local network and add new ones to devices.toml.

    Listens for the UDP discovery beacons every PixelBlaze broadcasts, connects
    to each address found to read its chip ID and name, and adds any device not
    already registered. Existing entries have their `name` and `host` refreshed;
    hand-written `notes` are never touched.

    Args:
        dry_run: Report what would be added or changed without writing the file.

    Returns the devices found, and what was added or refreshed.
    """
    from .config import load_devices
    from .discovery import listen_for_beacons

    found = listen_for_beacons()
    registry = load_devices()
    results: list[dict[str, Any]] = []
    changed = False

    for host in sorted(found):
        try:
            pb = Pixelblaze(host)
            try:
                config = read_config(pb)
            finally:
                pb._close()
            live = describe(config)
        except Exception as e:
            results.append({"host": host, "status": "unreachable", "error": str(e)})
            continue

        chip_id = live["chip_id"]
        known = registry.devices.get(chip_id)
        if known is None:
            action = "would add" if dry_run else "added"
        elif known.name != live["name"] or known.host != host:
            action = "would refresh" if dry_run else "refreshed"
        else:
            action = "unchanged"
        results.append(
            {"host": host, "chip_id": chip_id, "name": live["name"], "action": action, **live}
        )
        if not dry_run and action != "unchanged":
            if registry.set_fields(chip_id, name=live["name"], host=host):
                changed = True

    if changed:
        registry.save()
    return {
        "file": str(registry.path),
        "found": len(found),
        "devices": results,
        "registry_updated": changed,
        "dry_run": dry_run,
    }


# --- Local pattern files --------------------------------------------------


def pixelblaze_list_local_patterns(project: str | None = None) -> dict[str, Any]:
    """List local PixelBlaze pattern JS files and their deploy status.

    Reports, per file, whether it has been deployed, when, and whether the local
    file has been modified since. Useful for spotting patterns that need
    deploying or re-deploying.

    Args:
        project: A project folder name under `projects/`. Omit to list every
            project, grouped by project.
    """
    names = [project] if project else list_projects()
    grouped: dict[str, list[dict[str, Any]]] = {}
    for name in names:
        proj = load_project(name)
        rows: list[dict[str, Any]] = []
        if proj.patterns_dir.exists():
            for path in sorted(proj.patterns_dir.glob("*.js")):
                # A `<stem>.mapper.js` is that pattern's pixel map, not a pattern.
                if path.name.endswith(".mapper.js"):
                    continue
                try:
                    info = parse_pattern_file(path)
                    row = {
                        "file": path.name,
                        "name": info["name"],
                        "device_name": device_pattern_name(path.stem, proj),
                        "pattern_id": info["pattern_id"] or "(none)",
                        "deployed_to": info["device_name"] or info["device_id"] or "(never)",
                        "deployed_at": info["deployed_at"] or "(never)",
                        "modified_since_deployed": info["modified_since_deployed"],
                    }
                    if info["legacy_metadata"]:
                        row["needs_migration"] = True
                    rows.append(row)
                except Exception as e:
                    rows.append({"file": path.name, "error": str(e)})
        grouped[name] = rows
    return {"projects": grouped}


def pixelblaze_deploy_local_pattern(
    file_path: str, device: str | None = None, capture_preview: bool | None = None
) -> dict[str, str]:
    """Deploy a locally saved pattern JS file to a PixelBlaze device.

    Reads code from the file, creates or updates the pattern on the device, then
    stamps the file with the deployment timestamp and hash. Use this to deploy
    patterns created or edited in offline mode.

    Args:
        file_path: Path to the pattern JS file (absolute, or relative to the
            workspace root — the folder holding devices.toml).
        device: Which PixelBlaze to deploy to: a chip ID, a registered display
            name, or an IP address. Omit to redeploy to wherever this pattern
            last went, per its sidecar. Naming a device it has not been on
            creates it there afresh.
        capture_preview: Override the project's `preview_capture` setting for
            this call. False skips the ~6 s live thumbnail capture.
    """
    path = resolve_path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"Pattern file not found: {file_path}")

    project = project_for_path(path)
    info = parse_pattern_file(path)
    code = info["code"]
    existing_id = info["pattern_id"]
    # The local filename stem is the source of truth for the name, so renaming a
    # file locally propagates to the device on redeploy.
    name = device_pattern_name(path.stem, project)

    resolved = resolve_device(device, project=project, pattern_path=path)
    # An explicit device with no history always creates a new pattern there; it
    # never updates one under an ID minted on a different controller.
    entry = info["sidecar"].entry_for(resolved.chip_id) if resolved.chip_id else None
    existing_id = entry.pattern_id if entry else None

    with connect_resolved(resolved) as pb:
        pattern_id = _save_pattern(
            pb,
            code=code,
            name=name,
            pattern_id=existing_id,
            activate=existing_id is None,
            capture=_wants_preview(project, capture_preview),
        )
        controls = _read_controls(pb)

    write_pattern_file(path, code, path.stem)
    _record_deploy(path, code, pattern_id, resolved, controls)
    return {
        "id": pattern_id,
        "name": name,
        "file": path.name,
        "project": project.name,
        "device": resolved.label,
    }


# --- Device patterns ------------------------------------------------------


def pixelblaze_list_patterns(device: str) -> list[dict[str, str]]:
    """List all patterns stored on a PixelBlaze device.

    Args:
        device: Which PixelBlaze: a chip ID, a registered display name, or an IP.

    Returns a list of dicts with 'id' and 'name' keys.
    """
    with connect(device) as pb:
        patterns = pb.getPatternList()
        return [{"id": pid, "name": name} for pid, name in patterns.items()]


def pixelblaze_get_active_pattern(device: str) -> dict[str, str]:
    """Get the currently active (running) pattern on a PixelBlaze.

    Args:
        device: Which PixelBlaze: a chip ID, a registered display name, or an IP.

    Returns a dict with 'id' and 'name' of the active pattern.
    """
    with connect(device) as pb:
        active = pb.getActivePattern()
        if active is None:
            return {"id": "", "name": "(none)"}
        # Library may return a plain ID string or a dict like {id: name}
        if isinstance(active, str):
            pid = active
            patterns = pb.getPatternList()
            name = patterns.get(pid, "(unknown)") if isinstance(patterns, dict) else "(unknown)"
        else:
            pid, name = next(iter(active.items()))
        return {"id": pid, "name": name}


def pixelblaze_set_active_pattern(pattern_id: str, device: str) -> str:
    """Switch a PixelBlaze to run a specific pattern by its ID.

    Args:
        pattern_id: The pattern ID to activate (from pixelblaze_list_patterns).
        device: Which PixelBlaze: a chip ID, a registered display name, or an IP.

    Returns a confirmation message.
    """
    with connect(device) as pb:
        pb.setActivePattern(pattern_id)
        return f"Activated pattern {pattern_id}"


def pixelblaze_get_pattern_code(pattern_id: str, device: str | None = None) -> str:
    """Get the JavaScript source code of a pattern.

    Args:
        pattern_id: The pattern ID to retrieve code for.
        device: Which PixelBlaze to read from. Not needed in offline mode, where
            the local file for this ID is used instead.

    Returns the JavaScript source code string.
    """
    if is_offline():
        local = find_local_pattern_file(pattern_id)
        if local:
            return parse_pattern_file(local)["code"]
        raise RuntimeError(
            f"{OFFLINE_MSG}\n\n"
            f"No local file found for pattern ID '{pattern_id}'. "
            "Check the projects' patterns folders — the Pattern ID appears in the first "
            "comment line of each JS file. You can also read the file directly."
        )
    with connect(device) as pb:
        raw = pb.getPatternSourceCode(pattern_id)
        if raw is None:
            return f"No source code found for pattern {pattern_id}"
        return _unwrap_source(raw)


def pixelblaze_create_pattern(
    name: str,
    code: str,
    project: str,
    device: str | None = None,
    capture_preview: bool | None = None,
) -> dict[str, str]:
    """Create a new pattern on a PixelBlaze and activate it, saving a local copy
    in the project's patterns folder.

    In offline mode, saves the pattern locally as a pending file without
    deploying. Use pixelblaze_deploy_local_pattern to deploy it later.

    Args:
        name: Display name for the new pattern. If the project uses ordinals and
            the name does not start with a 2-digit one (e.g. "03 "), the next
            free ordinal is prepended. The project's `pattern_name_prefix` is
            added to the device's display name but never to the local filename.
        code: PixelBlaze JavaScript source code (must define a render(index) function).
        project: The project folder name under `projects/` this pattern belongs to.
        device: Which PixelBlaze to deploy to. Omit to use the project's most
            recently deployed device.
        capture_preview: Override the project's `preview_capture` setting for
            this call. False skips the ~6 s live thumbnail capture.

    Returns a dict with the new pattern's 'id', local 'name' and device name.
    """
    proj = load_project(project)
    # The filename stem, ordinal included. The device name adds the prefix.
    stem = canonical_pattern_name(name, proj)
    display_name = device_pattern_name(stem, proj)
    code = ensure_header(code, stem)

    if is_offline():
        path = new_pattern_file_path(stem, proj)
        write_pattern_file(path, code, stem)
        return {
            "id": "(not deployed)",
            "name": stem,
            "device_name": display_name,
            "project": proj.name,
            "status": "offline — not deployed",
            "file": str(path),
            "message": (
                f"Offline mode: pattern saved to {path.name} but not deployed. "
                f"Call pixelblaze_deploy_local_pattern('{path}', device=...) when a "
                "device is reachable."
            ),
        }

    resolved = resolve_device(device, project=proj)
    with connect_resolved(resolved) as pb:
        pattern_id = _save_pattern(
            pb,
            code=code,
            name=display_name,
            activate=True,
            capture=_wants_preview(proj, capture_preview),
        )
        controls = _read_controls(pb)

    path = new_pattern_file_path(stem, proj)
    write_pattern_file(path, code, stem)
    _record_deploy(path, code, pattern_id, resolved, controls)
    return {
        "id": pattern_id,
        "name": stem,
        "device_name": display_name,
        "project": proj.name,
        "file": path.name,
        "device": resolved.label,
    }


def pixelblaze_update_pattern(
    pattern_id: str, code: str, device: str | None = None, capture_preview: bool | None = None
) -> str:
    """Replace the JavaScript source code of an existing pattern, updating the
    local pattern JS file too.

    In offline mode, updates the local file only. It is then marked as
    modified-since-deployed, so it shows up in pixelblaze_list_local_patterns
    as needing re-deployment.

    Args:
        pattern_id: The ID of the pattern to update.
        code: New PixelBlaze JavaScript source code.
        device: Which PixelBlaze holds this pattern. Omit to use the device
            its sidecar last recorded.
        capture_preview: Override the project's `preview_capture` setting for
            this call. False skips the ~6 s live thumbnail capture.

    Returns a confirmation message.
    """
    local_path = find_local_pattern_file(pattern_id)
    project = project_for_path(local_path) if local_path else None

    if is_offline():
        if local_path is None:
            raise RuntimeError(
                f"{OFFLINE_MSG}\n\n"
                f"No local file found for pattern ID '{pattern_id}'. "
                "Cannot update without either a device connection or a local copy. "
                "Check the projects' patterns folders — the Pattern ID is in the first "
                "comment line of each JS file."
            )
        write_pattern_file(local_path, code, local_path.stem)
        return (
            f"Offline mode: updated local file {local_path.name} with new code. "
            "The device has not been updated. "
            f"Call pixelblaze_deploy_local_pattern('{local_path}', device=...) to deploy."
        )

    resolved = resolve_device(device, project=project, pattern_path=local_path)
    with connect_resolved(resolved) as pb:
        patterns = pb.getPatternList()
        name = patterns.get(pattern_id, pattern_id)
        code = ensure_header(code, local_path.stem if local_path else name)
        _save_pattern(
            pb,
            code=code,
            name=name,
            pattern_id=pattern_id,
            capture=_wants_preview(project, capture_preview),
        )
        controls = _read_controls(pb)

    if local_path is None:
        # An unknown pattern needs a project to land in; without one, the device
        # was updated but nothing local was written.
        return (
            f"Updated pattern '{name}' ({pattern_id}) on the device. No local file carries "
            "this ID, so nothing was saved locally. Use pixelblaze_create_pattern with a "
            "`project` to keep a local copy."
        )
    write_pattern_file(local_path, code, local_path.stem)
    _record_deploy(local_path, code, pattern_id, resolved, controls)
    return (
        f"Updated pattern '{name}' ({pattern_id}) on {resolved.label} — "
        f"wrote {local_path.name} and its sidecar"
    )


def pixelblaze_delete_pattern(pattern_id: str, device: str) -> str:
    """Delete a pattern from a PixelBlaze device.

    Removes it from the device only; no local file is ever deleted.

    Args:
        pattern_id: The ID of the pattern to delete.
        device: Which PixelBlaze: a chip ID, a registered display name, or an IP.

    Returns a confirmation message.
    """
    with connect(device) as pb:
        pb.deletePattern(pattern_id)
        return f"Deleted pattern {pattern_id}"


# --- Controls and device state -------------------------------------------


def pixelblaze_get_controls(device: str) -> list[dict[str, Any]]:
    """Get the UI controls for the currently active pattern on a device.

    Args:
        device: Which PixelBlaze: a chip ID, a registered display name, or an IP.

    Returns a list of control dicts, each with 'name' and 'value'. The controls
    correspond to exported slider/toggle/picker variables in the pattern code.
    """
    with connect(device) as pb:
        # getActiveControls() returns the live control values for the running
        # pattern as a flat {name: value} dict. (getPatternControls(id) only
        # returns values saved to flash, so freshly created patterns and unsaved
        # slider changes would appear empty.)
        controls = pb.getActiveControls() or {}
        return [{"name": k, "value": v} for k, v in controls.items()]


def pixelblaze_set_control(
    name: str, value: float | bool | list[float], device: str
) -> str:
    """Set the value of a UI control on the active pattern.

    Args:
        name: The control variable name (as it appears in pixelblaze_get_controls).
        value: A number for a slider (0.0-1.0), a boolean for a toggle, or a list
            of three floats for a colour picker — matching what the device stores.
        device: Which PixelBlaze: a chip ID, a registered display name, or an IP.

    Returns a confirmation message.
    """
    if isinstance(value, list) and len(value) != 3:
        raise ValueError(
            f"A list control value must have exactly 3 elements (a colour picker's "
            f"h, s, v); got {len(value)}."
        )
    with connect(device) as pb:
        # The client exposes setActiveControls(dict); there is no setControl().
        pb.setActiveControls({name: value})
        return f"Set control '{name}' to {value}"


def pixelblaze_regenerate_preview(pattern_id: str, device: str) -> str:
    """Regenerate the pattern-list thumbnail for a pattern already on a device.

    Captures a live preview from the pattern (activating it temporarily if it is
    not the running one) and re-saves the pattern with that thumbnail. Use this
    to backfill patterns saved without a preview image, which make the web UI's
    pattern list stall and show the "trouble loading preview images" dialog.

    Args:
        pattern_id: The ID of the pattern (from pixelblaze_list_patterns).
        device: Which PixelBlaze: a chip ID, a registered display name, or an IP.

    Returns a confirmation message.
    """
    with connect(device) as pb:
        patterns = pb.getPatternList()
        if pattern_id not in patterns:
            raise ValueError(f"No pattern with ID '{pattern_id}' on the device")
        name = patterns[pattern_id]
        code = _unwrap_source(pb.getPatternSourceCode(pattern_id))
        _save_pattern(pb, code=code, name=name, pattern_id=pattern_id, capture=True)
    return f"Regenerated preview for '{name}' ({pattern_id})"


def pixelblaze_get_device_info(device: str) -> dict[str, Any]:
    """Get hardware and runtime information about a PixelBlaze device.

    Args:
        device: Which PixelBlaze: a chip ID, a registered display name, or an IP.

    Returns a dict with the device's identity, hardware config, and runtime stats.
    """
    resolved = resolve_device(device)
    with connect_resolved(resolved) as pb:
        info: dict[str, Any] = {"host": resolved.host, **describe(read_config(pb))}
        stats = pb.getStatistics()
        info.update({
            "fps": pb.getFPS(),
            "uptime_s": pb.getUptime(),
            "version_major": pb.getVersionMajor(),
            "version_minor": pb.getVersionMinor(),
        })
        if stats:
            info["render_ms"] = stats.get("renderMs")
        return info


def pixelblaze_set_brightness(value: float, device: str) -> str:
    """Set the global brightness of a PixelBlaze.

    Args:
        value: Brightness level from 0.0 (off) to 1.0 (full brightness).
        device: Which PixelBlaze: a chip ID, a registered display name, or an IP.

    Returns a confirmation message.
    """
    value = max(0.0, min(1.0, value))
    with connect(device) as pb:
        pb.setBrightnessSlider(value)
        return f"Set brightness to {value:.2f}"
