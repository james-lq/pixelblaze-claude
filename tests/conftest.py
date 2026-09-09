"""Fixtures giving each test its own throwaway workspace.

`config` reads `devices.toml` and the project manifests at call time from
module-level paths, so pointing those paths at a temp directory is enough to
isolate a test. Nothing here touches a device.
"""

from pathlib import Path

import pytest

from pixelblaze_mcp import config


@pytest.fixture
def workspace(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """An empty workspace: `devices.toml` path and `projects/` under tmp_path."""
    projects = tmp_path / "projects"
    projects.mkdir()
    monkeypatch.setattr(config, "WORKSPACE_ROOT", tmp_path)
    monkeypatch.setattr(config, "DEVICES_FILE", tmp_path / "devices.toml")
    monkeypatch.setattr(config, "PROJECTS_DIR", projects)
    return tmp_path


@pytest.fixture
def make_project(workspace: Path):
    """Build a project folder with an optional manifest and pattern files."""

    def _make(name: str, manifest: str | None = None, patterns: list[str] = ()) -> config.Project:
        folder = workspace / "projects" / name
        (folder / "patterns").mkdir(parents=True)
        if manifest is not None:
            (folder / "project.toml").write_text(manifest, encoding="utf-8")
        for filename in patterns:
            (folder / "patterns" / filename).touch()
        return config.load_project(name)

    return _make


@pytest.fixture
def make_registry(workspace: Path):
    """Write a `devices.toml` and return the parsed registry."""

    def _make(content: str) -> config.Registry:
        (workspace / "devices.toml").write_text(content, encoding="utf-8")
        return config.load_devices()

    return _make
