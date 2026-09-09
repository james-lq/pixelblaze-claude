"""Pattern naming: the filename stem, the device display name, and back."""

import pytest

from pixelblaze_mcp.pattern_file import (
    canonical_pattern_name,
    device_pattern_name,
    new_pattern_file_path,
    stem_from_device_name,
)

PREFIX_DEFAULT = None  # no manifest key -> the folder name
PREFIX_OVERRIDE = 'pattern_name_prefix = "H26"\n'
PREFIX_EMPTY = 'pattern_name_prefix = ""\n'


@pytest.fixture
def project(make_project):
    """A project holding 01, 07 and a legacy 03-dash file, so the next free
    ordinal is 08."""

    def _build(manifest: str = "") -> object:
        return make_project(
            "H26-Finale",
            manifest=manifest,
            patterns=["01 Alpha.js", "07 Beta.js", "03-legacy.js"],
        )

    return _build


# --- Ordinals -------------------------------------------------------------


def test_auto_ordinal_is_the_next_free_one(project):
    assert canonical_pattern_name("Spark Chorus", project()) == "08 Spark Chorus"


def test_auto_ordinal_counts_legacy_dash_filenames(project, make_project):
    # 03-legacy.js is the dash form; a project with only it must yield 04.
    proj = make_project("legacy-only", manifest="", patterns=["03-legacy.js"])
    assert canonical_pattern_name("New", proj) == "04 New"


def test_ordinals_none_leaves_the_name_alone(project):
    proj = project('ordinals = "none"\n')
    assert canonical_pattern_name("Spark Chorus", proj) == "Spark Chorus"


@pytest.mark.parametrize("ordinals", ['ordinals = "auto"', 'ordinals = "none"'])
def test_explicit_ordinal_is_always_kept(project, ordinals):
    assert canonical_pattern_name("05 Already", project(ordinals + "\n")) == "05 Already"


def test_first_pattern_in_an_empty_project_is_01(make_project):
    assert canonical_pattern_name("First", make_project("empty", manifest="")) == "01 First"


def test_illegal_filename_characters_are_scrubbed(project):
    assert canonical_pattern_name('a/b:c*d?e"f', project()) == "08 a-b-c-d-e-f"


# --- Prefix and the device name round trip --------------------------------


@pytest.mark.parametrize(
    "manifest, expected_prefix",
    [(None, "H26-Finale"), (PREFIX_OVERRIDE, "H26"), (PREFIX_EMPTY, "")],
)
def test_prefix_resolution(project, manifest, expected_prefix):
    proj = project(manifest or "")
    assert proj.pattern_name_prefix == expected_prefix


@pytest.mark.parametrize("manifest", [None, PREFIX_OVERRIDE, PREFIX_EMPTY])
@pytest.mark.parametrize("ordinals", ['ordinals = "auto"', 'ordinals = "none"'])
def test_device_name_round_trips_to_the_stem(project, manifest, ordinals):
    proj = project((manifest or "") + ordinals + "\n")
    stem = canonical_pattern_name("Spark Chorus", proj)
    device_name = device_pattern_name(stem, proj)
    assert stem_from_device_name(device_name, proj) == stem


def test_device_name_is_prefix_space_stem(project):
    proj = project()
    assert device_pattern_name("08 Spark Chorus", proj) == "H26-Finale 08 Spark Chorus"


def test_empty_prefix_deploys_under_the_bare_stem(project):
    proj = project(PREFIX_EMPTY)
    assert device_pattern_name("08 Spark Chorus", proj) == "08 Spark Chorus"


def test_a_foreign_device_name_is_not_ours(project):
    """A pattern not carrying this project's prefix belongs to nobody here —
    the right answer for hand-made or downloaded patterns on a shared device."""
    proj = project()
    assert stem_from_device_name("Example: ui controls (lightning ZAP!)", proj) is None


def test_a_prefix_needs_its_separating_space(project):
    """`H26-FinaleX` starts with the prefix as a substring but is not ours."""
    proj = project()
    assert stem_from_device_name("H26-FinaleX 01 Nope", proj) is None


def test_the_local_filename_never_carries_the_prefix(project):
    proj = project()
    path = new_pattern_file_path(canonical_pattern_name("Spark Chorus", proj), proj)
    assert path.name == "08 Spark Chorus.js"
    assert proj.pattern_name_prefix not in path.name
    assert path.parent == proj.patterns_dir
