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
    """Phase 1 has no sidecar to fall back to, so this is always an error."""
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
