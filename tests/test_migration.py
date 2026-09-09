"""The one-off migration from in-file metadata blocks to sidecars."""

import importlib.util
from datetime import datetime, timezone
from pathlib import Path

import pytest

from pixelblaze_mcp import sidecar as sc
from pixelblaze_mcp.pattern_file import parse_pattern_file

_spec = importlib.util.spec_from_file_location(
    "migrate_layout", Path(__file__).parent.parent / "scripts" / "migrate_layout.py"
)
migrate_layout = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(migrate_layout)

DEVICE = "0x00AC056C"

STAMPED = """\
// 02 Aftershock — Pattern ID: mSXJ5etzaarWuZSPv
/*
  Effect: sparks.
*/
export function render(index) { hsv(0, 1, 1) }

// ---- pixelblaze-mcp metadata----
// @deployed: 2026-09-08T02:59:12Z
// @deployed-hash: 1e7d7a1f
// @modified-since-deployed: false
"""

# The shape that lost its name to the old "any leading // is a header" rule.
STAMPED_COMMENT_BODY = """\
// Fire — Pattern ID: y5qec8aPTGZWj6TmP
//
// Symmetric fire: both edges white-hot, center deep red.
export function render(index) { hsv(0, 1, 1) }

// ---- pixelblaze-mcp metadata----
// @deployed: 2026-09-06T02:25:16Z
// @deployed-hash: cf211d0c
// @modified-since-deployed: false
"""


@pytest.fixture
def project(make_project):
    return make_project("H26-Finale", manifest="")


def _write(project, name: str, content: str) -> Path:
    path = project.patterns_dir / name
    path.write_text(content, encoding="utf-8")
    return path


# --- With a device: a sidecar is written ---------------------------------


def test_migrating_with_a_device_writes_one_history_entry(project):
    path = _write(project, "02 Aftershock.js", STAMPED)
    assert migrate_layout.migrate_file(path, DEVICE, "PB LQ 56C SENSOR", False) == "migrated+sidecar"

    entry = sc.load(path).front
    assert entry.device_id == DEVICE
    assert entry.device_name == "PB LQ 56C SENSOR"
    assert entry.pattern_id == "mSXJ5etzaarWuZSPv"
    assert entry.deployed_at == datetime(2026, 9, 8, 2, 59, 12, tzinfo=timezone.utc)


def test_the_block_and_the_id_are_stripped(project):
    path = _write(project, "02 Aftershock.js", STAMPED)
    migrate_layout.migrate_file(path, DEVICE, "PB LQ 56C SENSOR", False)

    text = path.read_text()
    assert "pixelblaze-mcp metadata" not in text
    assert "Pattern ID" not in text
    assert text.splitlines()[0] == "// 02 Aftershock"
    assert "Effect: sparks." in text  # the author's own comment block survives


def test_a_migrated_file_does_not_read_as_modified(project):
    """The recorded hash is of what was actually written, so a purely cosmetic
    header rewrite must not flag the pattern as needing a redeploy."""
    path = _write(project, "02 Aftershock.js", STAMPED)
    migrate_layout.migrate_file(path, DEVICE, "PB LQ 56C SENSOR", False)
    assert parse_pattern_file(path)["modified_since_deployed"] is False


def test_the_name_survives_a_file_whose_body_starts_with_a_comment(project):
    """Regression: this shape lost its name for 25 files on the first run."""
    path = _write(project, "07-fire.js", STAMPED_COMMENT_BODY)
    migrate_layout.migrate_file(path, DEVICE, "PB LQ 56C SENSOR", False)

    lines = path.read_text().splitlines()
    assert lines[0] == "// Fire"
    assert "// Symmetric fire: both edges white-hot, center deep red." in lines


# --- Without a device: history is dropped --------------------------------


def test_migrating_without_a_device_writes_no_sidecar(project):
    path = _write(project, "07-fire.js", STAMPED_COMMENT_BODY)
    assert migrate_layout.migrate_file(path, None, None, False) == "migrated (no sidecar)"

    assert not sc.sidecar_path(path).exists()
    text = path.read_text()
    assert "Pattern ID" not in text
    assert "pixelblaze-mcp metadata" not in text
    assert text.splitlines()[0] == "// Fire"


def test_a_file_with_no_history_reads_as_never_deployed(project):
    path = _write(project, "07-fire.js", STAMPED_COMMENT_BODY)
    migrate_layout.migrate_file(path, None, None, False)

    info = parse_pattern_file(path)
    assert info["pattern_id"] is None
    assert info["modified_since_deployed"] is None
    assert info["legacy_metadata"] is False


# --- Idempotence and dry runs --------------------------------------------


def test_running_twice_skips_the_second_time(project):
    path = _write(project, "02 Aftershock.js", STAMPED)
    migrate_layout.migrate_file(path, DEVICE, "PB LQ 56C SENSOR", False)
    after_first = path.read_text()

    assert migrate_layout.migrate_file(path, DEVICE, "PB LQ 56C SENSOR", False) == "already-migrated"
    assert path.read_text() == after_first
    assert len(sc.load(path).entries) == 1


def test_a_dry_run_changes_nothing(project):
    path = _write(project, "02 Aftershock.js", STAMPED)
    assert migrate_layout.migrate_file(path, DEVICE, "PB LQ 56C SENSOR", True) == "would-migrate+sidecar"
    assert path.read_text() == STAMPED
    assert not sc.sidecar_path(path).exists()


def test_a_dry_run_without_a_device_says_so(project):
    path = _write(project, "07-fire.js", STAMPED_COMMENT_BODY)
    assert migrate_layout.migrate_file(path, None, None, True) == "would-migrate"


# --- Edge cases -----------------------------------------------------------


def test_a_pending_file_gets_no_sidecar(project):
    """Never deployed, so there is no deployment to record."""
    pending = STAMPED.replace("mSXJ5etzaarWuZSPv", "(pending)").replace(
        "// @deployed: 2026-09-08T02:59:12Z", "// @deployed: (pending)"
    )
    path = _write(project, "02 Aftershock.js", pending)
    assert migrate_layout.migrate_file(path, DEVICE, "PB LQ 56C SENSOR", False) == "migrated (no sidecar)"
    assert not sc.sidecar_path(path).exists()


def test_a_file_with_no_metadata_at_all_is_left_alone(project):
    plain = "/*\n  A hand-written pattern.\n*/\nexport function render(i) {}\n"
    path = _write(project, "04 Handwritten.js", plain)
    assert migrate_layout.migrate_file(path, DEVICE, "PB LQ 56C SENSOR", False) == "already-migrated"
    assert path.read_text() == plain
