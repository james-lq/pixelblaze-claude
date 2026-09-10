"""Which map a pattern wants, and when that map actually gets written."""

import pytest

from pixelblaze_mcp import pixel_map as pm

PROJECT_MAP = "function (pixelCount) { return [[0,0]] }\n"
PATTERN_MAP = "function (pixelCount) { return [[1,1]] }\n"


class FakePixelblaze:
    """Records what a deploy would do to the device's map.

    Phase 3 decides between three outcomes — leave it, push it, clear it — and
    that decision is the thing worth testing. A fake makes each one observable
    without a device.
    """

    def __init__(self, current: str = ""):
        self.current = current
        self.calls: list[tuple] = []

    # Stand-ins for the read path, which normally goes over HTTP.
    def getUrl(self, endpoint):
        return f"http://fake/{endpoint}"

    # ...and for the two write paths.
    def setMapFunction(self, text):
        self.calls.append(("setMapFunction", text))
        self.current = text
        return True

    def putFile(self, name, contents):
        self.calls.append(("putFile", name, contents))
        self.current = contents
        return True

    def setMapData(self, data, saveToFlash=True):
        self.calls.append(("setMapData", len(data), saveToFlash))
        return True


@pytest.fixture
def fake(monkeypatch):
    """A device whose map reads back whatever the fake is holding."""

    def _make(current: str = ""):
        pb = FakePixelblaze(current)
        monkeypatch.setattr(pm, "read_map", lambda p, timeout_s=None: p.current)
        return pb

    return _make


@pytest.fixture
def pattern(make_project):
    """A project with one pattern; the map files are added per test."""

    def _make(manifest: str = "", project_map: str | None = None, pattern_map: str | None = None):
        proj = make_project("H26-Barbie", manifest=manifest)
        js = proj.patterns_dir / "01 Sun Sparkle.js"
        js.write_text("// 01 Sun Sparkle\n", encoding="utf-8")
        if project_map is not None:
            (proj.path / "pixel-map.js").write_text(project_map, encoding="utf-8")
        if pattern_map is not None:
            (proj.patterns_dir / "01 Sun Sparkle.mapper.js").write_text(pattern_map, encoding="utf-8")
        return js, proj

    return _make


# --- Resolution order -----------------------------------------------------


def test_a_per_pattern_mapper_wins(pattern):
    js, proj = pattern(
        manifest='pixel_map = "pixel-map.js"\n', project_map=PROJECT_MAP, pattern_map=PATTERN_MAP
    )
    source, text = pm.map_for_pattern(js, proj)
    assert source.name == "01 Sun Sparkle.mapper.js"
    assert text == PATTERN_MAP


def test_the_project_map_is_the_default(pattern):
    js, proj = pattern(manifest='pixel_map = "pixel-map.js"\n', project_map=PROJECT_MAP)
    source, text = pm.map_for_pattern(js, proj)
    assert source.name == "pixel-map.js"
    assert text == PROJECT_MAP


def test_no_map_declared_resolves_to_empty_not_absent(pattern):
    """'No map' is an instruction to clear, not an absence of instruction."""
    js, proj = pattern(manifest="")
    source, text = pm.map_for_pattern(js, proj)
    assert source is None
    assert text == ""


def test_a_declared_map_that_is_missing_is_an_error(pattern):
    """Silently deploying no map because the file is missing would be worse."""
    js, proj = pattern(manifest='pixel_map = "pixel-map.js"\n')
    with pytest.raises(FileNotFoundError, match="pixel-map.js"):
        pm.map_for_pattern(js, proj)


def test_a_per_pattern_mapper_works_without_a_project_map(pattern):
    js, proj = pattern(manifest="", pattern_map=PATTERN_MAP)
    source, text = pm.map_for_pattern(js, proj)
    assert source.name == "01 Sun Sparkle.mapper.js"
    assert text == PATTERN_MAP


# --- Emptiness ------------------------------------------------------------


@pytest.mark.parametrize("text", ["", " ", "\n", "   \n\t "])
def test_whitespace_only_counts_as_no_map(text):
    """A map cleared through the web UI reads back as a single whitespace char."""
    assert pm.is_empty(text) is True


def test_a_real_map_is_not_empty():
    assert pm.is_empty(PROJECT_MAP) is False


def test_maps_differing_only_in_trailing_whitespace_hash_the_same():
    assert pm.map_hash(PROJECT_MAP) == pm.map_hash(PROJECT_MAP + "\n\n  ")


# --- The push decision ----------------------------------------------------


def test_a_matching_map_is_not_rewritten(fake, pattern):
    js, proj = pattern(manifest='pixel_map = "pixel-map.js"\n', project_map=PROJECT_MAP)
    pb = fake(PROJECT_MAP)
    result = pm.sync_map(pb, js, proj)
    assert result["action"] == "unchanged"
    assert pb.calls == []  # the whole point: a redeploy costs one read


def test_a_different_map_is_pushed(fake, pattern):
    js, proj = pattern(manifest='pixel_map = "pixel-map.js"\n', project_map=PROJECT_MAP)
    pb = fake(PATTERN_MAP)
    result = pm.sync_map(pb, js, proj)
    assert result["action"] == "pushed"
    assert result["map_hash"] == pm.map_hash(PROJECT_MAP)
    assert pb.calls == [("setMapFunction", PROJECT_MAP)]


def test_a_project_with_no_map_clears_the_device(fake, pattern):
    """The stale-map fix: a 1D project must not inherit another project's map."""
    js, proj = pattern(manifest="")
    pb = fake(PROJECT_MAP)
    result = pm.sync_map(pb, js, proj)
    assert result["action"] == "cleared"
    assert result["previous_hash"] == pm.map_hash(PROJECT_MAP)
    # Clearing has to drop the compiled map data too, or render2D keeps using
    # coordinates from a map the device no longer reports.
    assert [c[0] for c in pb.calls] == ["putFile", "setMapData"]
    assert pb.calls[1][1] == 0  # empty map data


def test_no_map_wanted_and_none_present_does_nothing(fake, pattern):
    js, proj = pattern(manifest="")
    pb = fake("\n")  # a device whose map was cleared through the web UI
    result = pm.sync_map(pb, js, proj)
    assert result["action"] == "unchanged (no map)"
    assert pb.calls == []


def test_the_per_pattern_map_is_what_gets_pushed(fake, pattern):
    js, proj = pattern(
        manifest='pixel_map = "pixel-map.js"\n', project_map=PROJECT_MAP, pattern_map=PATTERN_MAP
    )
    pb = fake("")
    result = pm.sync_map(pb, js, proj)
    assert pb.calls == [("setMapFunction", PATTERN_MAP)]
    assert result["source"].endswith("01 Sun Sparkle.mapper.js")


def test_write_map_clears_rather_than_compiling_an_empty_function(fake):
    """setMapFunction would try to run "" as JavaScript and fail."""
    pb = fake(PROJECT_MAP)
    pm.write_map(pb, "")
    assert "setMapFunction" not in [c[0] for c in pb.calls]
