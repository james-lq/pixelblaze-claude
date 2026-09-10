"""Whole-project deployment: what gets skipped, and what a failure does."""

from datetime import datetime, timezone

import pytest

from pixelblaze_mcp import pixelblaze_tools as tools
from pixelblaze_mcp import sidecar as sc
from pixelblaze_mcp.config import Device

CHIP = "0x00AC00A4"
CODE = "// {stem}\nexport function render(index) {{ hsv(0, 1, 1) }}\n"


@pytest.fixture
def project(make_project, monkeypatch):
    """A project with three patterns, and a stubbed single-pattern deploy so the
    only thing under test is which patterns get chosen."""
    proj = make_project("H26-Barbie", manifest="")
    for stem in ("01 A", "02 B", "03 C"):
        (proj.patterns_dir / f"{stem}.js").write_text(CODE.format(stem=stem), encoding="utf-8")

    monkeypatch.setattr(
        tools, "resolve_device",
        lambda *a, **k: Device(name="PBLQ 0A4", host="10.0.0.1", chip_id=CHIP),
    )

    calls: list[str] = []

    def fake_deploy(path, device=None, capture_preview=None, deploy_map=True, controls="auto"):
        from pathlib import Path

        calls.append(Path(path).name)
        return {
            "id": "id-" + Path(path).stem,
            "name": Path(path).stem,
            "pixel_map": "unchanged (no map)",
            "controls": "read back",
        }

    monkeypatch.setattr(tools, "pixelblaze_deploy_local_pattern", fake_deploy)
    return proj, calls


def _record(proj, stem, *, code=None):
    """Mark a pattern as already deployed to CHIP with the given code."""
    path = proj.patterns_dir / f"{stem}.js"
    s = sc.load(path)
    s.record(
        device_id=CHIP,
        pattern_id="id-" + stem,
        deployed_hash=sc.content_hash(code if code is not None else path.read_text()),
        deployed_at=datetime(2026, 9, 9, tzinfo=timezone.utc),
    )
    s.save()


def test_every_pattern_goes_when_none_have_history(project):
    proj, calls = project
    result = tools.pixelblaze_deploy_project("H26-Barbie")
    assert calls == ["01 A.js", "02 B.js", "03 C.js"]
    assert result["summary"] == {"total": 3, "deployed": 3, "skipped": 0, "failed": 0}


def test_unchanged_patterns_are_skipped(project):
    proj, calls = project
    _record(proj, "01 A")
    _record(proj, "02 B")
    result = tools.pixelblaze_deploy_project("H26-Barbie")

    assert calls == ["03 C.js"]
    assert result["summary"]["skipped"] == 2
    assert [p["action"] for p in result["patterns"]] == [
        "skipped (unchanged)", "skipped (unchanged)", "deployed",
    ]


def test_an_edited_pattern_is_not_skipped(project):
    proj, calls = project
    _record(proj, "01 A", code="something else entirely")
    tools.pixelblaze_deploy_project("H26-Barbie")
    assert "01 A.js" in calls


def test_only_modified_false_forces_everything(project):
    """What a prefix change or a move to a fresh controller needs."""
    proj, calls = project
    _record(proj, "01 A")
    _record(proj, "02 B")
    result = tools.pixelblaze_deploy_project("H26-Barbie", only_modified=False)
    assert calls == ["01 A.js", "02 B.js", "03 C.js"]
    assert result["summary"]["skipped"] == 0


def test_history_on_a_different_device_does_not_count_as_deployed(project):
    """Moving a project to a new controller must deploy everything."""
    proj, calls = project
    for stem in ("01 A", "02 B", "03 C"):
        path = proj.patterns_dir / f"{stem}.js"
        s = sc.load(path)
        s.record(
            device_id="0x00AC056C",
            pattern_id="other-" + stem,
            deployed_hash=sc.content_hash(path.read_text()),
            deployed_at=datetime(2026, 9, 9, tzinfo=timezone.utc),
        )
        s.save()
    tools.pixelblaze_deploy_project("H26-Barbie")
    assert calls == ["01 A.js", "02 B.js", "03 C.js"]


def test_one_failure_does_not_strand_the_rest(project, monkeypatch):
    proj, calls = project
    real = tools.pixelblaze_deploy_local_pattern

    def flaky(path, **kwargs):
        if "02 B" in str(path):
            raise RuntimeError("device said no")
        return real(path, **kwargs)

    monkeypatch.setattr(tools, "pixelblaze_deploy_local_pattern", flaky)
    result = tools.pixelblaze_deploy_project("H26-Barbie")

    assert result["summary"] == {"total": 3, "deployed": 2, "skipped": 0, "failed": 1}
    failed = [p for p in result["patterns"] if p["action"] == "failed"]
    assert failed[0]["file"] == "02 B.js" and "device said no" in failed[0]["error"]
    assert "03 C.js" in calls  # the run continued past the failure


def test_mapper_files_are_not_treated_as_patterns(project):
    proj, calls = project
    (proj.patterns_dir / "01 A.mapper.js").write_text("function (n) { return [] }", encoding="utf-8")
    result = tools.pixelblaze_deploy_project("H26-Barbie")
    assert result["summary"]["total"] == 3
    assert "01 A.mapper.js" not in calls


def test_an_empty_project_is_not_an_error(make_project, monkeypatch):
    make_project("empty", manifest="")
    monkeypatch.setattr(
        tools, "resolve_device",
        lambda *a, **k: Device(name="PBLQ 0A4", host="10.0.0.1", chip_id=CHIP),
    )
    result = tools.pixelblaze_deploy_project("empty")
    assert result["summary"]["total"] == 0


def test_the_result_names_the_prefix_in_force(project):
    """A prefix change is the main reason to run this, so report what was used."""
    result = tools.pixelblaze_deploy_project("H26-Barbie")
    assert result["prefix"] == "H26-Barbie"
