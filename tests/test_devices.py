"""The device registry: chip IDs, parsing, validation, resolution, and rewrites."""

import pytest

from pixelblaze_mcp.config import (
    Registry,
    format_chip_id,
    load_devices,
    resolve_device,
)

TWO_DEVICES = """\
[devices.0x00AC00A4]
name = "PB LQ 0A4 SENSOR"
host = "10.0.1.106"

[devices.0x00AC056C]
name = "PB LQ 56C SENSOR"
host = "10.0.1.107"
"""


# --- Chip ID formatting ---------------------------------------------------


@pytest.mark.parametrize(
    "value, expected",
    [
        (11272356, "0x00AC00A4"),          # the int form getConfig reports
        ("11272356", "0x00AC00A4"),        # all digits -> decimal
        ("0x00ac00a4", "0x00AC00A4"),      # prefixed hex, lower case
        ("0X00AC00A4", "0x00AC00A4"),
        ("00AC00A4", "0x00AC00A4"),        # bare hex, has letters
        ("ac00a4", "0x00AC00A4"),          # short forms zero-pad
        (0, "0x00000000"),
        (0xFFFFFFFF, "0xFFFFFFFF"),
    ],
)
def test_chip_id_canonical_form(value, expected):
    assert format_chip_id(value) == expected


@pytest.mark.parametrize("value", ["", "nope", "0xTODO", "0x1234567890", "PB LQ 0A4", True])
def test_chip_id_rejects_junk(value):
    with pytest.raises(ValueError):
        format_chip_id(value)


def test_chip_id_rejects_out_of_range():
    with pytest.raises(ValueError, match="out of range"):
        format_chip_id(0x1_0000_0000)


# --- Parsing and validation -----------------------------------------------


def test_missing_file_is_an_empty_registry(workspace):
    assert len(load_devices()) == 0


def test_entries_are_keyed_by_canonical_chip_id(make_registry):
    registry = make_registry('[devices.00ac00a4]\nname = "x"\nhost = "h"\n')
    assert list(registry.devices) == ["0x00AC00A4"]
    assert registry.devices["0x00AC00A4"].chip_id == "0x00AC00A4"


def test_a_misspelled_field_is_an_error_not_a_silent_default(make_registry):
    with pytest.raises(ValueError) as e:
        make_registry('[devices.0x00AC00A4]\nnaem = "typo"\nhost = "10.0.1.106"\n')
    assert "0x00AC00A4" in str(e.value)
    assert "naem" in str(e.value)


def test_an_unparseable_table_key_names_the_fix(make_registry):
    with pytest.raises(ValueError, match="discover_devices"):
        make_registry('[devices.0xTODO]\nname = "x"\nhost = "h"\n')


def test_a_missing_host_is_an_error(make_registry):
    with pytest.raises(ValueError, match="host"):
        make_registry('[devices.0x00AC00A4]\nname = "x"\n')


def test_notes_are_read_verbatim(make_registry):
    registry = make_registry(
        '[devices.0x00AC00A4]\nhost = "h"\nnotes = """\n- **50 px**, GRB\n"""\n'
    )
    assert registry.devices["0x00AC00A4"].notes == "- **50 px**, GRB\n"


# --- resolve_device -------------------------------------------------------


@pytest.mark.parametrize(
    "arg",
    ["0x00AC00A4", "0X00ac00a4", "00AC00A4", "11272356", "PB LQ 0A4 SENSOR", "pb lq 0a4 sensor"],
)
def test_resolves_by_chip_id_and_by_name(make_registry, arg):
    registry = make_registry(TWO_DEVICES)
    assert resolve_device(arg, registry=registry).chip_id == "0x00AC00A4"


def test_a_registered_host_resolves_to_its_entry(make_registry):
    """So it still gets chip ID verification, rather than being treated as an
    unknown box reached by address."""
    registry = make_registry(TWO_DEVICES)
    device = resolve_device("10.0.1.107", registry=registry)
    assert device.chip_id == "0x00AC056C"
    assert device.ad_hoc is False


@pytest.mark.parametrize("arg", ["10.0.1.199", "pb-bench.local"])
def test_an_unregistered_address_is_ad_hoc(make_registry, arg):
    device = resolve_device(arg, registry=make_registry(TWO_DEVICES))
    assert device.ad_hoc is True
    assert device.host == arg
    assert device.chip_id is None


def test_an_ambiguous_name_is_an_error_listing_the_ids(make_registry):
    registry = make_registry(
        '[devices.0x00AC00A4]\nname = "bench"\nhost = "a"\n'
        '[devices.0x00AC056C]\nname = "BENCH"\nhost = "b"\n'
    )
    with pytest.raises(ValueError) as e:
        resolve_device("bench", registry=registry)
    assert "0x00AC00A4" in str(e.value) and "0x00AC056C" in str(e.value)


def test_an_unknown_single_label_name_errors_rather_than_dialling_it(make_registry):
    """A typo'd device name should list the registry, not time out connecting."""
    with pytest.raises(ValueError, match="Unknown device"):
        resolve_device("bench", registry=make_registry(TWO_DEVICES))


def test_an_unknown_chip_id_says_so(make_registry):
    with pytest.raises(ValueError, match="No device with chip ID 0xDEADBEEF"):
        resolve_device("0xDEADBEEF", registry=make_registry(TWO_DEVICES))


def test_omitting_the_device_lists_what_is_registered(make_registry):
    """With no pattern or project to infer from, there is no history to consult."""
    with pytest.raises(ValueError) as e:
        resolve_device(None, registry=make_registry(TWO_DEVICES))
    assert "PB LQ 0A4 SENSOR" in str(e.value) and "PB LQ 56C SENSOR" in str(e.value)


def test_an_empty_device_string_is_rejected(make_registry):
    with pytest.raises(ValueError, match="empty"):
        resolve_device("   ", registry=make_registry(TWO_DEVICES))


# --- Rewrites preserve everything the tooling does not own ----------------

COMMENTED_REGISTRY = """\
# Registry header comment, line one.
# Registry header comment, line two.

[devices.0x00AC00A4]
# A comment above name.
name = "old name"
host = "10.0.1.106"
notes = \"\"\"
Hand-written **notes** that tooling must never touch.
\"\"\"

# A trailing comment after the first entry.
"""


def _comment_lines(text: str) -> list[str]:
    return [line for line in text.splitlines() if line.lstrip().startswith("#")]


def test_a_no_op_refresh_leaves_the_file_byte_identical(make_registry, workspace):
    registry = make_registry(COMMENTED_REGISTRY)
    before = (workspace / "devices.toml").read_text()
    assert registry.set_fields("0x00AC00A4", name="old name", host="10.0.1.106") is False
    registry.save()
    assert (workspace / "devices.toml").read_text() == before


def test_a_refresh_touches_only_the_owned_keys(make_registry, workspace):
    registry = make_registry(COMMENTED_REGISTRY)
    before = (workspace / "devices.toml").read_text()
    assert registry.set_fields("0x00AC00A4", name="new name", host="10.0.1.150") is True
    registry.save()
    after = (workspace / "devices.toml").read_text()

    assert _comment_lines(after) == _comment_lines(before)
    assert "Hand-written **notes** that tooling must never touch." in after
    assert 'name = "new name"' in after and 'host = "10.0.1.150"' in after
    assert "old name" not in after
    # Everything that is not one of the two owned lines is unchanged.
    changed = set(before.splitlines()) - set(after.splitlines())
    assert changed == {'name = "old name"', 'host = "10.0.1.106"'}


def test_a_new_entry_is_appended_and_reparses(make_registry, workspace):
    registry = make_registry(COMMENTED_REGISTRY)
    assert registry.set_fields("0x00AC056C", name="PB LQ 56C SENSOR", host="10.0.1.107") is True
    registry.save()

    reloaded = load_devices()
    assert set(reloaded.devices) == {"0x00AC00A4", "0x00AC056C"}
    assert reloaded.devices["0x00AC056C"].host == "10.0.1.107"
    assert _comment_lines((workspace / "devices.toml").read_text()) == _comment_lines(
        COMMENTED_REGISTRY
    )


def test_set_fields_normalises_the_key(make_registry):
    """A caller passing the int form must not create a second entry."""
    registry = make_registry(COMMENTED_REGISTRY)
    registry.set_fields(format_chip_id(11272356), name="x")
    assert list(registry.devices) == ["0x00AC00A4"]


def test_summary_lists_every_device(make_registry):
    assert make_registry(TWO_DEVICES).summary().count("\n") == 1


def test_summary_of_an_empty_registry_says_so(workspace):
    assert "no devices registered" in load_devices().summary()


# --- Inferring the device from deployment history -------------------------


def _deployed(project, name, device_id, day):
    """A pattern in `project` last deployed to `device_id` on 2026-09-<day>."""
    from datetime import datetime, timezone

    from pixelblaze_mcp import sidecar as sc

    path = project.patterns_dir / name
    path.write_text(f"// {path.stem}\n", encoding="utf-8")
    s = sc.load(path)
    s.record(
        device_id=device_id,
        pattern_id="id-" + name,
        deployed_hash="aaaaaaaa",
        deployed_at=datetime(2026, 9, day, 12, 0, 0, tzinfo=timezone.utc),
    )
    s.save()
    return path


def test_the_device_comes_from_the_pattern_s_own_history(make_registry, make_project):
    """A redeploy needs no argument: the front sidecar entry names the device."""
    registry = make_registry(TWO_DEVICES)
    proj = make_project("H26-Finale", manifest="")
    path = _deployed(proj, "01 Alpha.js", "0x00AC056C", 9)

    device = resolve_device(None, registry=registry, project=proj, pattern_path=path)
    assert device.chip_id == "0x00AC056C"


def test_the_pattern_s_history_wins_over_the_project_s(make_registry, make_project):
    registry = make_registry(TWO_DEVICES)
    proj = make_project("H26-Finale", manifest="")
    _deployed(proj, "02 Beta.js", "0x00AC00A4", 11)  # the project's most recent
    path = _deployed(proj, "01 Alpha.js", "0x00AC056C", 9)

    device = resolve_device(None, registry=registry, project=proj, pattern_path=path)
    assert device.chip_id == "0x00AC056C"


def test_a_new_pattern_falls_back_to_the_project_s_last_device(make_registry, make_project):
    registry = make_registry(TWO_DEVICES)
    proj = make_project("H26-Finale", manifest="")
    _deployed(proj, "01 Alpha.js", "0x00AC00A4", 8)
    _deployed(proj, "02 Beta.js", "0x00AC056C", 11)
    fresh = proj.patterns_dir / "03 Gamma.js"
    fresh.write_text("// 03 Gamma\n", encoding="utf-8")

    device = resolve_device(None, registry=registry, project=proj, pattern_path=fresh)
    assert device.chip_id == "0x00AC056C"  # the most recent across the project


def test_an_explicit_device_overrides_the_history(make_registry, make_project):
    registry = make_registry(TWO_DEVICES)
    proj = make_project("H26-Finale", manifest="")
    path = _deployed(proj, "01 Alpha.js", "0x00AC056C", 9)

    device = resolve_device("0x00AC00A4", registry=registry, project=proj, pattern_path=path)
    assert device.chip_id == "0x00AC00A4"


def test_history_naming_an_unregistered_device_is_an_error(make_registry, make_project):
    registry = make_registry(TWO_DEVICES)
    proj = make_project("H26-Finale", manifest="")
    path = _deployed(proj, "01 Alpha.js", "0xDEADBEEF", 9)

    with pytest.raises(ValueError) as e:
        resolve_device(None, registry=registry, project=proj, pattern_path=path)
    assert "0xDEADBEEF" in str(e.value)
    assert "discover_devices" in str(e.value)


def test_a_project_with_no_history_still_errors(make_registry, make_project):
    registry = make_registry(TWO_DEVICES)
    proj = make_project("H26-Finale", manifest="")
    fresh = proj.patterns_dir / "01 Alpha.js"
    fresh.write_text("// 01 Alpha\n", encoding="utf-8")

    with pytest.raises(ValueError, match="no deployment history"):
        resolve_device(None, registry=registry, project=proj, pattern_path=fresh)
