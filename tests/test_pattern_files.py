"""Pattern file headers, and finding a file by a Pattern ID in its sidecar."""

from datetime import datetime, timezone

from pixelblaze_mcp import sidecar as sc
from pixelblaze_mcp.pattern_file import (
    ensure_header,
    find_local_pattern_file,
    has_legacy_block,
    parse_legacy_block,
    parse_pattern_file,
    strip_legacy_block,
    write_pattern_file,
)

CODE = "export function render(index) { hsv(0, 1, 1) }\n"

LEGACY = """\
// 01 Alpha — Pattern ID: aaa111
export function render(index) { hsv(0, 1, 1) }

// ---- pixelblaze-mcp metadata----
// @deployed: 2026-09-06T02:25:16Z
// @deployed-hash: cf211d0c
// @modified-since-deployed: false
"""


def _deploy(path, code, pattern_id, device_id="0x00AC00A4", when=None):
    """Write a pattern and record one deployment, as a deploy would."""
    write_pattern_file(path, code, path.stem)
    s = sc.load(path)
    s.record(
        device_id=device_id,
        device_name="PB LQ 0A4 SENSOR",
        pattern_id=pattern_id,
        # The hash covers the file content as sent to the device, header included.
        deployed_hash=sc.content_hash(path.read_text()),
        deployed_at=when or datetime(2026, 9, 9, 12, 0, 0, tzinfo=timezone.utc),
    )
    s.save()
    return s


# --- The header line ------------------------------------------------------


def test_the_header_is_name_only():
    assert ensure_header(CODE, "08 Spark Chorus").splitlines()[0] == "// 08 Spark Chorus"


def test_a_leading_comment_that_is_not_the_name_still_gets_a_header():
    """Regression: treating any leading `//` line as the header lost the pattern
    name for every file whose second line was also a comment."""
    authored = f"//\n// Symmetric fire: both edges white-hot.\n{CODE}"
    out = ensure_header(authored, "07 Fire")
    assert out.splitlines()[0] == "// 07 Fire"
    assert "// Symmetric fire: both edges white-hot." in out


def test_ensure_header_is_idempotent():
    once = ensure_header(CODE, "08 Spark Chorus")
    assert ensure_header(once, "08 Spark Chorus") == once


def test_a_legacy_header_still_counts_as_a_header():
    """So a not-yet-migrated file does not gain a second header line."""
    already = f"// 01 Alpha — Pattern ID: aaa111\n{CODE}"
    assert ensure_header(already, "01 Alpha") == already


def test_write_pattern_file_stores_no_metadata(make_project):
    proj = make_project("H26-Finale", manifest="")
    path = proj.patterns_dir / "08 Spark Chorus.js"
    write_pattern_file(path, CODE, "08 Spark Chorus")
    text = path.read_text()
    assert text.splitlines()[0] == "// 08 Spark Chorus"
    assert "pixelblaze-mcp metadata" not in text
    assert "Pattern ID" not in text


def test_write_pattern_file_creates_the_patterns_folder(make_project):
    proj = make_project("H26-Finale", manifest="")
    proj.patterns_dir.rmdir()
    path = proj.patterns_dir / "01 First.js"
    write_pattern_file(path, CODE, "01 First")
    assert path.exists()


# --- parse_pattern_file reads its facts from the sidecar ------------------


def test_a_pattern_with_no_sidecar_reads_as_never_deployed(make_project):
    proj = make_project("H26-Finale", manifest="")
    path = proj.patterns_dir / "08 Spark Chorus.js"
    write_pattern_file(path, CODE, "08 Spark Chorus")

    info = parse_pattern_file(path)
    assert info["pattern_id"] is None
    assert info["deployed_at"] is None
    assert info["modified_since_deployed"] is None  # nothing to compare against


def test_a_freshly_deployed_pattern_is_not_modified(make_project):
    proj = make_project("H26-Finale", manifest="")
    path = proj.patterns_dir / "08 Spark Chorus.js"
    _deploy(path, CODE, "aaa111")

    info = parse_pattern_file(path)
    assert info["pattern_id"] == "aaa111"
    assert info["device_id"] == "0x00AC00A4"
    assert info["device_name"] == "PB LQ 0A4 SENSOR"
    assert info["modified_since_deployed"] is False


def test_editing_the_file_makes_it_read_as_modified(make_project):
    proj = make_project("H26-Finale", manifest="")
    path = proj.patterns_dir / "08 Spark Chorus.js"
    _deploy(path, CODE, "aaa111")
    path.write_text(path.read_text().replace("hsv(0,", "hsv(0.5,"), encoding="utf-8")
    assert parse_pattern_file(path)["modified_since_deployed"] is True


def test_the_name_comes_from_the_header(make_project):
    proj = make_project("H26-Finale", manifest="")
    path = proj.patterns_dir / "08 Spark Chorus.js"
    write_pattern_file(path, CODE, "08 Spark Chorus")
    assert parse_pattern_file(path)["name"] == "08 Spark Chorus"


# --- Legacy files are still readable until migrated ----------------------


def test_a_legacy_file_is_recognised(make_project):
    proj = make_project("H26-Finale", manifest="")
    path = proj.patterns_dir / "01 Alpha.js"
    path.write_text(LEGACY, encoding="utf-8")

    info = parse_pattern_file(path)
    assert info["legacy_metadata"] is True
    assert info["name"] == "01 Alpha"
    assert info["pattern_id"] == "aaa111"  # from the header, there being no sidecar
    assert "pixelblaze-mcp metadata" not in info["code"]


def test_parse_legacy_block_extracts_what_migration_needs():
    parsed = parse_legacy_block(LEGACY)
    assert parsed == {
        "pattern_id": "aaa111",
        "name": "01 Alpha",
        "deployed_at": "2026-09-06T02:25:16Z",
        "deployed_hash": "cf211d0c",
    }


def test_strip_legacy_block_removes_the_trailing_block():
    stripped = strip_legacy_block(LEGACY)
    assert "pixelblaze-mcp metadata" not in stripped
    assert stripped.startswith("// 01 Alpha — Pattern ID: aaa111")


def test_a_migrated_file_is_not_flagged_legacy(make_project):
    proj = make_project("H26-Finale", manifest="")
    path = proj.patterns_dir / "08 Spark Chorus.js"
    write_pattern_file(path, CODE, "08 Spark Chorus")
    assert has_legacy_block(path.read_text()) is False
    assert parse_pattern_file(path)["legacy_metadata"] is False


# --- Finding a file by ID, across every project ---------------------------


def test_finds_the_file_by_an_id_in_its_sidecar(make_project):
    a = make_project("H26-Finale", manifest="")
    b = make_project("test-pattern", manifest="")
    _deploy(a.patterns_dir / "01 Alpha.js", CODE, "aaa111")
    _deploy(b.patterns_dir / "01 Beta.js", CODE, "bbb222")

    assert find_local_pattern_file("aaa111").name == "01 Alpha.js"
    assert find_local_pattern_file("bbb222").name == "01 Beta.js"


def test_finds_a_pattern_by_its_id_on_a_second_device(make_project):
    """A pattern on two devices has two IDs; either one must find the file."""
    proj = make_project("H26-Finale", manifest="")
    path = proj.patterns_dir / "01 Alpha.js"
    s = _deploy(path, CODE, "aaa111", device_id="0x00AC00A4")
    s.record(
        device_id="0x00AC056C",
        device_name="PB LQ 56C SENSOR",
        pattern_id="bbb222",
        deployed_hash=sc.content_hash(path.read_text()),
        deployed_at=datetime(2026, 9, 10, 12, 0, 0, tzinfo=timezone.utc),
    )
    s.save()

    assert find_local_pattern_file("aaa111") == path
    assert find_local_pattern_file("bbb222") == path


def test_an_unknown_id_is_none(make_project):
    make_project("H26-Finale", manifest="")
    assert find_local_pattern_file("nosuchid") is None


def test_no_projects_directory_is_none(workspace):
    (workspace / "projects").rmdir()
    assert find_local_pattern_file("aaa111") is None
