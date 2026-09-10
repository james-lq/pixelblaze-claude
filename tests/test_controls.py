"""Control values: merging, per-pattern targeting, and seed-vs-read-back."""

from datetime import datetime, timezone

import pytest

from pixelblaze_mcp import controls as ctl
from pixelblaze_mcp import sidecar as sc

A = "0x00AC00A4"
B = "0x00AC056C"


class FakePixelblaze:
    """A device that records every call, so a deploy's control handling is
    observable without hardware.

    Models the two behaviours that make this awkward for real: `setControls`
    applies to whichever pattern is *active*, and it replaces the stored map
    rather than merging into it.
    """

    def __init__(self, active: str = "sparkle", stored: dict | None = None):
        self.active = active
        self.stored: dict[str, dict] = stored or {}
        self.calls: list[tuple] = []

    def getActivePattern(self):
        return self.active

    def setActivePattern(self, pattern_id):
        self.calls.append(("setActivePattern", pattern_id))
        self.active = pattern_id

    def getActiveControls(self):
        return dict(self.stored.get(self.active, {}))

    def getPatternControls(self, pattern_id):
        # The nested envelope the real device returns.
        return {"controls": {pattern_id: dict(self.stored.get(pattern_id, {}))}}

    def setActiveControls(self, values, saveToFlash=False):
        self.calls.append(("setActiveControls", self.active, dict(values), saveToFlash))
        # Replaces, never merges — the device behaviour this module works around.
        self.stored[self.active] = dict(values)


# --- The merge that the device does not do -------------------------------


def test_setting_one_control_leaves_the_others_alone():
    """The bug this fixes: writing one control used to reset the rest to
    uninitialised memory."""
    pb = FakePixelblaze(stored={"sparkle": {"sliderDensity": 0.7, "sliderGlow": 0.2}})
    result = ctl.write_controls(pb, "sparkle", {"sliderGlow": 0.6})

    assert result == {"sliderDensity": 0.7, "sliderGlow": 0.6}
    assert pb.stored["sparkle"] == {"sliderDensity": 0.7, "sliderGlow": 0.6}


def test_merge_false_replaces_the_whole_map():
    """Right only when restoring a complete recorded set."""
    pb = FakePixelblaze(stored={"sparkle": {"sliderDensity": 0.7, "sliderGlow": 0.2}})
    assert ctl.write_controls(pb, "sparkle", {"sliderGlow": 0.6}, merge=False) == {
        "sliderGlow": 0.6
    }


def test_values_are_saved_to_flash_by_default():
    pb = FakePixelblaze(stored={"sparkle": {}})
    ctl.write_controls(pb, "sparkle", {"sliderGlow": 0.6})
    assert pb.calls[-1][3] is True


def test_control_value_types_are_not_coerced():
    pb = FakePixelblaze(stored={"sparkle": {}})
    values = {"sliderX": 0.5, "toggleY": True, "hsvPickerZ": [0.1, 0.2, 0.3]}
    assert ctl.write_controls(pb, "sparkle", values) == values


# --- Writing to a pattern that is not the one running --------------------


def test_writing_another_pattern_activates_it_and_puts_the_old_one_back():
    pb = FakePixelblaze(active="sparkle", stored={"chaser": {"sliderWidth": 0.3}})
    ctl.write_controls(pb, "chaser", {"sliderWidth": 0.5})

    assert [c[0] for c in pb.calls] == ["setActivePattern", "setActiveControls", "setActivePattern"]
    assert pb.calls[0][1] == "chaser"
    assert pb.calls[-1][1] == "sparkle"
    assert pb.active == "sparkle"
    assert pb.stored["chaser"] == {"sliderWidth": 0.5}


def test_writing_the_running_pattern_does_not_switch_anything():
    pb = FakePixelblaze(active="sparkle", stored={"sparkle": {}})
    ctl.write_controls(pb, "sparkle", {"sliderGlow": 0.6})
    assert [c[0] for c in pb.calls] == ["setActiveControls"]


def test_writing_nothing_is_a_read():
    pb = FakePixelblaze(active="sparkle", stored={"sparkle": {"sliderGlow": 0.6}})
    assert ctl.write_controls(pb, "sparkle", {}) == {"sliderGlow": 0.6}
    assert pb.calls == []


# --- Reading the right pattern's values ----------------------------------


def test_reading_the_running_pattern_uses_its_live_values():
    pb = FakePixelblaze(active="sparkle", stored={"sparkle": {"sliderDensity": 0.895}})
    assert ctl.read_controls(pb, "sparkle") == {"sliderDensity": 0.895}


def test_reading_another_pattern_gets_its_own_values():
    """Regression: this used to return the running pattern's controls."""
    pb = FakePixelblaze(
        active="sparkle",
        stored={"sparkle": {"sliderDensity": 0.895}, "chaser": {"sliderWidth": 0.3}},
    )
    assert ctl.read_controls(pb, "chaser") == {"sliderWidth": 0.3}


def test_a_read_failure_is_not_fatal():
    class Broken(FakePixelblaze):
        def getActivePattern(self):
            raise RuntimeError("websocket died")

    assert ctl.read_controls(Broken(), "chaser") == {}


@pytest.mark.parametrize(
    "raw, expected",
    [
        ({"controls": {"chaser": {"a": 1}}}, {"a": 1}),   # the real nested shape
        ({"controls": {"other": {"a": 1}}}, {"a": 1}),    # keyed by what came back
        ({"a": 1}, {"a": 1}),                            # already flat
        ({"controls": {}}, {}),
        ({}, {}),
        (None, {}),
    ],
)
def test_the_response_envelope_is_flattened(raw, expected):
    assert ctl.flatten_pattern_controls(raw, "chaser") == expected


# --- Seeding a new device vs leaving a known one alone -------------------


@pytest.fixture
def history(make_project):
    """A pattern deployed to device A with controls recorded."""
    proj = make_project("H26-Barbie", manifest="")
    js = proj.patterns_dir / "01 Sun Sparkle.js"
    js.write_text("// 01 Sun Sparkle\n", encoding="utf-8")

    def _build(*entries):
        s = sc.load(js)
        for chip, pid, day, controls in entries:
            s.record(
                device_id=chip,
                pattern_id=pid,
                deployed_hash="aaaaaaaa",
                deployed_at=datetime(2026, 9, day, tzinfo=timezone.utc),
                controls=controls,
            )
        return s

    return _build


def test_a_first_deploy_to_a_new_device_seeds_from_history(history):
    """The fix for a fresh pattern reading uninitialised memory."""
    s = history((A, "pid-a", 8, {"sliderDensity": 0.895}))
    assert ctl.seed_values(s, B, ctl.AUTO) == {"sliderDensity": 0.895}


def test_a_redeploy_to_a_known_device_pushes_nothing(history):
    """Its own values win, so web-UI tuning is never clobbered."""
    s = history((A, "pid-a", 8, {"sliderDensity": 0.895}))
    assert ctl.seed_values(s, A, ctl.AUTO) is None


def test_a_first_deploy_with_no_history_at_all_seeds_nothing(history):
    s = history()
    assert ctl.seed_values(s, A, ctl.AUTO) is None


def test_push_forces_values_onto_a_known_device(history):
    """The restore-after-reflash case."""
    s = history((A, "pid-a", 8, {"sliderDensity": 0.895}))
    assert ctl.seed_values(s, A, ctl.PUSH) == {"sliderDensity": 0.895}


def test_push_prefers_the_device_s_own_recorded_values(history):
    s = history(
        (A, "pid-a", 8, {"sliderDensity": 0.1}),
        (B, "pid-b", 9, {"sliderDensity": 0.9}),
    )
    assert ctl.seed_values(s, A, ctl.PUSH) == {"sliderDensity": 0.1}


def test_push_falls_back_to_the_most_recent_entry(history):
    s = history((A, "pid-a", 8, {"sliderDensity": 0.1}))
    assert ctl.seed_values(s, B, ctl.PUSH) == {"sliderDensity": 0.1}


def test_skip_never_writes(history):
    s = history((A, "pid-a", 8, {"sliderDensity": 0.895}))
    assert ctl.seed_values(s, B, ctl.SKIP) is None


def test_seeding_takes_the_most_recent_entry(history):
    s = history(
        (A, "pid-a", 8, {"sliderDensity": 0.1}),
        (B, "pid-b", 11, {"sliderDensity": 0.9}),
    )
    assert ctl.seed_values(s, "0xDEADBEEF", ctl.AUTO) == {"sliderDensity": 0.9}
