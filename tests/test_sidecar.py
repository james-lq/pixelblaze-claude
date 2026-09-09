"""Sidecar round trips: history ordering, value types, and comment survival."""

from datetime import datetime, timezone

import pytest

from pixelblaze_mcp import sidecar as sc

A = "0x00AC00A4"
B = "0x00AC056C"


def _at(day: int) -> datetime:
    return datetime(2026, 9, day, 12, 0, 0, tzinfo=timezone.utc)


@pytest.fixture
def js(make_project):
    proj = make_project("H26-Finale", manifest="")
    return proj.patterns_dir / "02 Aftershock.js"


def _record(s, device_id, pattern_id, day, **kw):
    return s.record(
        device_id=device_id,
        pattern_id=pattern_id,
        deployed_hash="a2b066c7",
        deployed_at=_at(day),
        **kw,
    )


# --- Creating and reading -------------------------------------------------


def test_a_pattern_with_no_sidecar_has_no_history(js):
    s = sc.load(js)
    assert s.entries == []
    assert s.front is None
    assert s.modified_since_deployed("anything") is None


def test_the_sidecar_sits_beside_the_pattern(js):
    assert sc.sidecar_path(js).name == "02 Aftershock.sidecar.toml"
    assert sc.sidecar_path(js).parent == js.parent


def test_a_new_sidecar_carries_the_explanatory_comment(js):
    s = sc.load(js)
    _record(s, A, "aaa111", 8)
    s.save()
    assert s.path.read_text().startswith("# Written by the pixelblaze-mcp tooling")


def test_round_trip_through_tomlkit(js):
    s = sc.load(js)
    _record(s, A, "aaa111", 8, device_name="PB LQ 0A4 SENSOR", map_hash="d41d8cd9")
    s.save()

    reloaded = sc.load(js)
    entry = reloaded.front
    assert entry.device_id == A
    assert entry.pattern_id == "aaa111"
    assert entry.device_name == "PB LQ 0A4 SENSOR"
    assert entry.map_hash == "d41d8cd9"
    assert entry.deployed_at == _at(8)


# --- Per-device history ---------------------------------------------------


def test_a_second_device_gets_its_own_entry(js):
    s = sc.load(js)
    _record(s, A, "aaa111", 8)
    _record(s, B, "bbb222", 9)
    s.save()

    reloaded = sc.load(js)
    assert [e.device_id for e in reloaded.entries] == [B, A]
    assert reloaded.entry_for(A).pattern_id == "aaa111"
    assert reloaded.entry_for(B).pattern_id == "bbb222"


def test_redeploying_updates_in_place_and_moves_to_the_front(js):
    s = sc.load(js)
    _record(s, A, "aaa111", 8)
    _record(s, B, "bbb222", 9)
    _record(s, A, "aaa111", 10)  # redeploy to the first device
    s.save()

    reloaded = sc.load(js)
    assert [e.device_id for e in reloaded.entries] == [A, B]
    assert len(reloaded.entries) == 2  # updated, not appended
    assert reloaded.front.deployed_at == _at(10)


def test_the_front_entry_is_the_most_recent(js):
    s = sc.load(js)
    _record(s, A, "aaa111", 10)
    _record(s, B, "bbb222", 8)  # recorded later but deployed earlier
    s.save()
    assert sc.load(js).front.device_id == A


def test_an_entry_can_be_removed(js):
    s = sc.load(js)
    _record(s, A, "aaa111", 8)
    _record(s, B, "bbb222", 9)
    assert s.remove(A) is True
    assert s.remove(A) is False
    s.save()
    assert [e.device_id for e in sc.load(js).entries] == [B]


def test_a_device_id_is_normalised_on_lookup(js):
    s = sc.load(js)
    _record(s, A, "aaa111", 8)
    assert s.entry_for("0x00ac00a4") is not None
    assert s.entry_for("11272356") is not None


# --- Control values keep their own types ---------------------------------


def test_control_value_types_round_trip_unchanged(js):
    controls = {
        "sliderCycleSeconds": 0.42,
        "channelSync": False,
        "toggleOn": True,
        "hsvPickerCrystal": [0.727, 0.683, 0.718],
    }
    s = sc.load(js)
    _record(s, A, "aaa111", 8, controls=controls)
    s.save()

    back = sc.load(js).front.controls
    assert back == controls
    assert isinstance(back["sliderCycleSeconds"], float)
    assert isinstance(back["channelSync"], bool)
    assert isinstance(back["hsvPickerCrystal"], list)
    assert all(isinstance(v, float) for v in back["hsvPickerCrystal"])


def test_omitting_controls_on_redeploy_keeps_the_recorded_ones(js):
    s = sc.load(js)
    _record(s, A, "aaa111", 8, controls={"sliderSpeed": 0.5})
    _record(s, A, "aaa111", 9)  # no controls passed
    s.save()
    assert sc.load(js).front.controls == {"sliderSpeed": 0.5}


def test_passing_controls_replaces_them(js):
    s = sc.load(js)
    _record(s, A, "aaa111", 8, controls={"sliderSpeed": 0.5})
    _record(s, A, "aaa111", 9, controls={"sliderSpeed": 0.9})
    s.save()
    assert sc.load(js).front.controls == {"sliderSpeed": 0.9}


# --- Drift detection ------------------------------------------------------


def test_modified_since_deployed_compares_hashes(js):
    code = "// 02 Aftershock\nrender(i) {}\n"
    s = sc.load(js)
    s.record(
        device_id=A, pattern_id="aaa111", deployed_hash=sc.content_hash(code), deployed_at=_at(8)
    )
    s.save()

    reloaded = sc.load(js)
    assert reloaded.modified_since_deployed(code) is False
    assert reloaded.modified_since_deployed(code + "// edited\n") is True


def test_trailing_whitespace_does_not_count_as_a_change(js):
    code = "// 02 Aftershock\nrender(i) {}\n"
    assert sc.content_hash(code) == sc.content_hash(code + "\n\n  ")


# --- Comments and validation ---------------------------------------------


def test_the_top_of_file_comment_survives_a_rewrite(js):
    s = sc.load(js)
    _record(s, A, "aaa111", 8)
    s.save()
    hand_edited = "# My own note about this pattern.\n" + s.path.read_text()
    s.path.write_text(hand_edited, encoding="utf-8")

    s2 = sc.load(js)
    _record(s2, B, "bbb222", 9)
    s2.save()
    assert "# My own note about this pattern." in s.path.read_text()


def test_a_misspelled_field_is_an_error(js):
    sc.sidecar_path(js).parent.mkdir(parents=True, exist_ok=True)
    sc.sidecar_path(js).write_text(
        '[[deployment_history]]\ndevice_id = "0x00AC00A4"\npattern_id = "a"\n'
        'deployed_at = 2026-09-08T02:59:12Z\ndeployed_hash = "x"\ndeployd_name = "typo"\n',
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="deployd_name"):
        sc.load(js)


def test_a_bad_device_id_names_the_entry(js):
    sc.sidecar_path(js).parent.mkdir(parents=True, exist_ok=True)
    sc.sidecar_path(js).write_text(
        '[[deployment_history]]\ndevice_id = "not-an-id"\npattern_id = "a"\n'
        'deployed_at = 2026-09-08T02:59:12Z\ndeployed_hash = "x"\n',
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="entry 1"):
        sc.load(js)


# --- Project-level lookup -------------------------------------------------


def test_most_recent_device_across_a_project(make_project):
    proj = make_project("H26-Finale", manifest="")
    for name, device, day in [("01 A.js", A, 8), ("02 B.js", B, 11), ("03 C.js", A, 9)]:
        s = sc.load(proj.patterns_dir / name)
        _record(s, device, "id-" + name, day)
        s.save()
    assert sc.most_recent_device(proj.patterns_dir) == B


def test_most_recent_device_of_an_empty_project(make_project):
    proj = make_project("H26-Finale", manifest="")
    assert sc.most_recent_device(proj.patterns_dir) is None
