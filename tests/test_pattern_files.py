"""Pattern file headers, stamping, and finding a file by its Pattern ID."""

from pixelblaze_mcp.pattern_file import (
    ensure_header,
    find_local_pattern_file,
    parse_pattern_file,
    stamp_file,
)

CODE = "export function render(index) { hsv(0, 1, 1) }\n"


def test_ensure_header_prepends_a_pending_id():
    out = ensure_header(CODE, "08 Spark Chorus")
    assert out.splitlines()[0] == "// 08 Spark Chorus — Pattern ID: (pending)"


def test_ensure_header_leaves_an_existing_header_alone():
    already = f"// 01 Alpha — Pattern ID: abc123\n{CODE}"
    assert ensure_header(already, "08 Spark Chorus") == already


def test_stamp_then_parse_round_trips_and_reads_unmodified(make_project):
    proj = make_project("H26-Finale", manifest="")
    path = proj.patterns_dir / "08 Spark Chorus.js"
    stamp_file(path, ensure_header(CODE, "08 Spark Chorus"), "abc123", "2026-09-09T12:00:00Z")

    info = parse_pattern_file(path)
    assert info["pattern_id"] == "abc123"
    assert info["name"] == "08 Spark Chorus"
    assert info["deployed_at"] == "2026-09-09T12:00:00Z"
    # A freshly stamped file must not immediately read as modified.
    assert info["modified_since_deployed"] is False


def test_editing_a_stamped_file_makes_it_read_as_modified(make_project):
    proj = make_project("H26-Finale", manifest="")
    path = proj.patterns_dir / "08 Spark Chorus.js"
    stamp_file(path, ensure_header(CODE, "08 Spark Chorus"), "abc123", "2026-09-09T12:00:00Z")
    path.write_text(path.read_text().replace("hsv(0, 1, 1)", "hsv(0.5, 1, 1)"), encoding="utf-8")
    assert parse_pattern_file(path)["modified_since_deployed"] is True


def test_a_pending_file_is_not_modified_since_deployed(make_project):
    proj = make_project("H26-Finale", manifest="")
    path = proj.patterns_dir / "08 Spark Chorus.js"
    stamp_file(path, ensure_header(CODE, "08 Spark Chorus"), "(pending)", None)
    info = parse_pattern_file(path)
    assert info["deployed_at"] == "(pending)"
    assert info["modified_since_deployed"] is False


def test_stamping_creates_the_patterns_folder(make_project, workspace):
    """A project whose patterns/ does not exist yet must not fail the first save."""
    proj = make_project("H26-Finale", manifest="")
    proj.patterns_dir.rmdir()
    path = proj.patterns_dir / "01 First.js"
    stamp_file(path, ensure_header(CODE, "01 First"), "abc123", "2026-09-09T12:00:00Z")
    assert path.exists()


# --- Finding a file by ID, across every project ---------------------------


def test_finds_the_file_in_any_project(make_project):
    """Phase 1 drops the single-project pin, so the scan spans projects/*."""
    a = make_project("H26-Finale", manifest="")
    b = make_project("test-pattern", manifest="")
    stamp_file(a.patterns_dir / "01 Alpha.js", ensure_header(CODE, "01 Alpha"), "aaa111", "t")
    stamp_file(b.patterns_dir / "01 Beta.js", ensure_header(CODE, "01 Beta"), "bbb222", "t")

    assert find_local_pattern_file("aaa111").name == "01 Alpha.js"
    assert find_local_pattern_file("bbb222").name == "01 Beta.js"


def test_an_unknown_id_is_none(make_project):
    make_project("H26-Finale", manifest="")
    assert find_local_pattern_file("nosuchid") is None


def test_no_projects_directory_is_none(workspace):
    (workspace / "projects").rmdir()
    assert find_local_pattern_file("aaa111") is None


def test_a_headerless_update_keeps_the_file_findable(make_project):
    """Regression: update_pattern used to write the caller's code straight to the
    local file. Code arriving without a header line then stripped it, orphaning
    the file from the Pattern ID that phase 1 looks it up by."""
    proj = make_project("H26-Finale", manifest="")
    path = proj.patterns_dir / "01 Alpha.js"
    stamp_file(path, ensure_header(CODE, "01 Alpha"), "aaa111", "2026-09-09T12:00:00Z")

    # What the fixed tool does before writing: re-add the header if absent.
    headerless = "export function render(index) { hsv(0.5, 1, 1) }\n"
    stamp_file(path, ensure_header(headerless, path.stem, "aaa111"), "aaa111", "t")

    assert parse_pattern_file(path)["pattern_id"] == "aaa111"
    assert find_local_pattern_file("aaa111") == path
