"""Project manifests: defaults, validation, and locating a file's project."""

import pytest

from pixelblaze_mcp.config import list_projects, load_project, project_for_path, resolve_path


def test_an_absent_manifest_is_all_defaults(make_project):
    proj = make_project("H26-Finale", manifest=None)
    assert proj.pattern_name_prefix == "H26-Finale"  # the folder name
    assert proj.ordinals == "auto"
    assert proj.preview_capture is True
    assert proj.pixel_map_path is None


def test_an_empty_manifest_is_all_defaults(make_project):
    proj = make_project("H26-Finale", manifest="")
    assert proj.pattern_name_prefix == "H26-Finale"
    assert proj.ordinals == "auto"


def test_a_fully_commented_manifest_is_all_defaults(make_project):
    """The shipped form: every token present but commented out at its default."""
    proj = make_project(
        "H26-Finale",
        manifest='#pattern_name_prefix = "H26-Finale"\n#ordinals = "auto"\n#preview_capture = true\n',
    )
    assert proj.pattern_name_prefix == "H26-Finale"
    assert proj.ordinals == "auto"
    assert proj.preview_capture is True


def test_an_empty_prefix_is_meaningful_not_missing(make_project):
    """`""` means deploy under bare filenames; only an absent key means "folder name"."""
    proj = make_project("H26-Finale", manifest='pattern_name_prefix = ""\n')
    assert proj.pattern_name_prefix == ""


def test_overrides_are_read(make_project):
    proj = make_project(
        "H26-Finale",
        manifest=(
            'pattern_name_prefix = "H26"\n'
            'ordinals = "none"\n'
            'pixel_map = "pixel-map.js"\n'
            "preview_capture = false\n"
        ),
    )
    assert proj.pattern_name_prefix == "H26"
    assert proj.ordinals == "none"
    assert proj.preview_capture is False
    assert proj.pixel_map_path == proj.path / "pixel-map.js"


def test_a_misspelled_key_is_an_error_not_a_silent_default(make_project):
    with pytest.raises(ValueError, match="ordnals"):
        make_project("H26-Finale", manifest='ordnals = "none"\n')


def test_an_invalid_ordinals_value_is_rejected(make_project):
    with pytest.raises(ValueError, match="ordinals"):
        make_project("H26-Finale", manifest='ordinals = "sometimes"\n')


def test_a_prefix_with_illegal_filename_characters_is_rejected(make_project):
    """The prefix ends up in a device name that has to map back to a filename."""
    with pytest.raises(ValueError, match="pattern_name_prefix"):
        make_project("H26-Finale", manifest='pattern_name_prefix = "H26/Finale"\n')


def test_an_unknown_project_lists_the_known_ones(make_project):
    make_project("H26-Finale", manifest="")
    make_project("test-pattern", manifest="")
    with pytest.raises(ValueError) as e:
        load_project("nope")
    assert "H26-Finale" in str(e.value) and "test-pattern" in str(e.value)


def test_list_projects_is_sorted(make_project):
    make_project("test-pattern", manifest="")
    make_project("H26-Finale", manifest="")
    assert list_projects() == ["H26-Finale", "test-pattern"]


def test_list_projects_on_an_empty_workspace(workspace):
    assert list_projects() == []


# --- Paths ----------------------------------------------------------------


def test_a_file_path_implies_its_project(make_project):
    proj = make_project("H26-Finale", manifest="")
    path = proj.patterns_dir / "01 Alpha.js"
    path.touch()
    assert project_for_path(path).name == "H26-Finale"


def test_a_path_outside_any_project_is_an_error(workspace):
    stray = workspace / "stray.js"
    stray.touch()
    with pytest.raises(ValueError, match="not inside a project folder"):
        project_for_path(stray)


def test_a_relative_path_resolves_from_the_workspace_root(workspace):
    assert resolve_path("projects/H26-Finale/patterns/x.js") == (
        workspace / "projects/H26-Finale/patterns/x.js"
    )


def test_an_absolute_path_is_left_alone(workspace, tmp_path):
    assert resolve_path(tmp_path / "elsewhere.js") == tmp_path / "elsewhere.js"
