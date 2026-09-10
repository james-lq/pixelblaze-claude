"""Reading and writing a pattern's UI control values.

Two awkward facts about the device API shape everything here:

1. **There is only one writer, and it targets the running pattern.**
   `setControls` applies to whatever is active, so writing another pattern's
   controls means making it active first and putting back what was running.

2. **That writer replaces, it does not merge.** Sending one control silently
   resets every other control on that pattern to uninitialised memory. So a
   merge has to happen on this side: read the current map, layer the new values
   over it, and send the whole thing back.

Control values are not all floats. Sliders are floats, toggles are booleans,
and colour pickers are arrays of three floats. Nothing here coerces between
them; the sidecar stores each as its own TOML type.
"""

import logging
from typing import Any

logger = logging.getLogger(__name__)

# What to do about controls during a deploy.
AUTO = "auto"    # seed a device that has none, otherwise read back what is there
PUSH = "push"    # force the sidecar's values onto the device
SKIP = "skip"    # do not read or write controls at all
MODES = (AUTO, PUSH, SKIP)


def flatten_pattern_controls(raw: Any, pattern_id: str) -> dict[str, Any]:
    """Flatten what `getPatternControls()` actually returns.

    Its docstring promises `{name: value}`, but it hands back the raw websocket
    response, which nests the values under the pattern ID:
    `{"controls": {"<patternId>": {name: value}}}`. Storing that shape in a
    sidecar would bury the values a level down under a device-specific ID.
    """
    if not isinstance(raw, dict) or not raw:
        return {}
    inner = raw.get("controls")
    if isinstance(inner, dict):
        by_id = inner.get(pattern_id)
        if isinstance(by_id, dict):
            return dict(by_id)
        # Some firmware keys it by the pattern it actually returned.
        if len(inner) == 1:
            only = next(iter(inner.values()))
            return dict(only) if isinstance(only, dict) else {}
        return {}
    return dict(raw)


def read_controls(pb, pattern_id: str) -> dict[str, Any]:
    """The control values belonging to `pattern_id`.

    Which call to use depends on whether this pattern is the one running.
    `getActiveControls()` returns the *running* pattern's live values, including
    slider moves not yet saved to flash — right when the pattern in question is
    active, and badly wrong otherwise, since it would file some other pattern's
    values under this one's name. `getPatternControls()` is per-pattern but only
    sees what reached flash.
    """
    try:
        if pb.getActivePattern() == pattern_id:
            return dict(pb.getActiveControls() or {})
        return flatten_pattern_controls(pb.getPatternControls(pattern_id), pattern_id)
    except Exception as e:  # a control read must never fail a deploy
        logger.warning("Could not read control values for %s: %s", pattern_id, e)
        return {}


def write_controls(
    pb,
    pattern_id: str,
    values: dict[str, Any],
    *,
    merge: bool = True,
    save: bool = True,
) -> dict[str, Any]:
    """Set control values on a specific pattern and return the resulting map.

    `merge=True` layers `values` over what the pattern already has, which is the
    behaviour every caller wants and the device does not provide. `merge=False`
    replaces the map wholesale, which is only right when restoring a complete
    recorded set.

    If `pattern_id` is not the running pattern it is activated for the write and
    the previous pattern is restored afterwards, since the device offers no way
    to write another pattern's controls in place.
    """
    if not values and merge:
        return read_controls(pb, pattern_id)

    previously_active = pb.getActivePattern()
    must_switch = previously_active != pattern_id
    if must_switch:
        pb.setActivePattern(pattern_id)
    try:
        current = dict(pb.getActiveControls() or {}) if merge else {}
        merged = {**current, **values}
        pb.setActiveControls(merged, saveToFlash=save)
        return merged
    finally:
        if must_switch and previously_active:
            pb.setActivePattern(previously_active)


def seed_values(sidecar, chip_id: str, mode: str) -> dict[str, Any] | None:
    """The control values a deploy should push, or None to push nothing.

    - `auto` seeds only a device with no history for this pattern, taking the
      most recent entry's values. That is the fix for a first deploy reading
      uninitialised memory, and it leaves a device that already has values
      alone so web-UI tuning is never clobbered.
    - `push` forces values on regardless: this device's own recorded set if it
      has one, else the most recent. That is the restore-after-reflash case.
    - `skip` never writes.
    """
    if mode == SKIP:
        return None

    own = sidecar.entry_for(chip_id) if chip_id else None
    front = sidecar.front

    if mode == PUSH:
        source = own or front
        return dict(source.controls) if source and source.controls else None

    if own is not None:
        return None  # known device: leave its own values alone
    return dict(front.controls) if front and front.controls else None
