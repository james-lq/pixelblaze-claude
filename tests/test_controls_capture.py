"""Which pattern's control values a deploy records."""

from pixelblaze_mcp.pixelblaze_tools import _read_controls


class FakeDevice:
    """A device running `active`, holding per-pattern values in flash."""

    def __init__(self, active, flash):
        self.active = active
        self.flash = flash
        self.live = {"sliderDensity": 0.895, "sliderSpeed": 0.5}

    def getActivePattern(self):
        return self.active

    def getActiveControls(self):
        return self.live

    def getPatternControls(self, pattern_id):
        return self.flash.get(pattern_id)


FLASH = {"chaser": {"inputNumberSecondsPerColor": 3, "sliderWidth": 0.3}}


def test_deploying_the_running_pattern_captures_its_live_values():
    """Live values include slider moves not yet saved to flash."""
    pb = FakeDevice(active="sparkle", flash=FLASH)
    assert _read_controls(pb, "sparkle") == {"sliderDensity": 0.895, "sliderSpeed": 0.5}


def test_deploying_a_pattern_that_is_not_running_reads_its_own_values():
    """Regression: this used to return the *running* pattern's controls, filing
    one pattern's values under another pattern's name in the sidecar."""
    pb = FakeDevice(active="sparkle", flash=FLASH)
    assert _read_controls(pb, "chaser") == {"inputNumberSecondsPerColor": 3, "sliderWidth": 0.3}


def test_a_pattern_with_nothing_in_flash_records_nothing():
    """A first deploy has no saved values; recording an empty map is honest,
    and beats recording the running pattern's."""
    pb = FakeDevice(active="sparkle", flash=FLASH)
    assert _read_controls(pb, "brand-new") == {}


def test_a_device_error_does_not_fail_the_deploy():
    class Broken(FakeDevice):
        def getActivePattern(self):
            raise RuntimeError("websocket died")

    assert _read_controls(Broken("sparkle", FLASH), "chaser") == {}


# --- getPatternControls returns a shape its docstring does not promise -------


def test_the_nested_websocket_shape_is_flattened():
    """Regression: getPatternControls() hands back the raw response,
    {"controls": {"<patternId>": {...}}}, not the flat dict it documents."""

    class Nested(FakeDevice):
        def getPatternControls(self, pattern_id):
            return {"controls": {pattern_id: {"inputNumberSecondsPerColor": 3}}}

    assert _read_controls(Nested("sparkle", {}), "chaser") == {"inputNumberSecondsPerColor": 3}


def test_an_already_flat_response_is_passed_through():
    class Flat(FakeDevice):
        def getPatternControls(self, pattern_id):
            return {"sliderWidth": 0.3}

    assert _read_controls(Flat("sparkle", {}), "chaser") == {"sliderWidth": 0.3}


def test_an_empty_controls_envelope_yields_nothing():
    class Empty(FakeDevice):
        def getPatternControls(self, pattern_id):
            return {"controls": {}}

    assert _read_controls(Empty("sparkle", {}), "chaser") == {}
