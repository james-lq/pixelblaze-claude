# Plan 02 — Evaluate `pixelblaze-client` upstream, and the issues we work around

Status: **not started.** This is a record of defects and surprises found in `pixelblaze-client` while building the multi-device tooling, plus what to do about them.

Everything here was found against **`pixelblaze-client` 1.1.7** talking to two Pixelblaze v3 (`pb32`) controllers on **firmware 3.67**. Every workaround described is already in the tree and working; nothing here is urgent. The point of the plan is to stop carrying the workarounds silently, and to decide whether they belong upstream.

Package: <https://github.com/zranger1/pixelblaze-client>, MIT. Dependency chain as installed: `websocket-client 1.9.0`, `requests 2.33.0`, `mini-racer 0.14.1`, `pytz`, `click`, `json5`, `lzstring`.

## 1. First: is there a newer version, or a better fork?

Do this before anything else — several findings below may already be fixed upstream, and fixing them locally would be wasted work.

1. Check PyPI for a release newer than **1.1.7**, and read the changelog between the two.
2. Check the GitHub repo for activity: open issues and PRs matching the findings in section 2, whether `main` is ahead of the last release, and whether the project still has a maintainer.
3. Look for maintained forks. The Pixelblaze community is small and it is plausible that a fork carries fixes the original does not.
4. Search the Electromage forum for known client issues. `PBZ` (already in `TODO.md` as worth evaluating) is a separate unofficial CLI/JS library and may have solved some of the same problems differently: <https://forum.electromage.com/t/pbz-an-unofficial-cli-js-library-for-pixelblaze-headless-pattern-compiling/4742>

Outcome to decide: **upgrade**, **switch fork**, **contribute fixes upstream**, or **keep the local workarounds**. Sections 2 and 3 are the input to that decision.

## 2. Confirmed defects

Line numbers are into `pixelblaze/pixelblaze.py` at 1.1.7.

### 2.1 `getConfigExpander()` never returns when there is no expander (line 1822)

The worst of these, because it hangs the process with no error.

```python
def getConfigExpander(self) -> dict:
    while True:
        if not self.latestExpander is None: return self.latestExpander
        ignored = self.getConfigSettings()
```

`getConfigSettings()` deliberately gives up waiting for the expander packet when a device has no expander:

```python
if self.latestSequencer is not None and ignored is None: break
```

So on a device without an output expander, `latestExpander` is never populated and the loop spins forever, re-fetching config. Hit on the first exploratory call against a live device and initially misread as a network problem.

**Workaround in tree:** `device.read_config()` calls `getConfigSettings()` and then reads `pb.latestExpander` directly, which is already populated as a side effect. `getConfigExpander()` is never called. Documented in `src/pixelblaze_mcp/device.py`.

**Upstream fix:** bound the loop, or return `None`/`{}` when `getConfigSettings()` reports no expander.

### 2.2 HTTP calls have no timeout (lines 831, 846, and `getMapFunction` at 1595)

`getFile` / `putFile` are `requests.get` / `requests.post` with no `timeout=`, so a device that stops answering mid-request blocks the caller indefinitely — `requests` has no default timeout. `getMapFunction()` is `getFile("/pixelmap.txt")`, so it inherits this, and that is what hung a second exploratory call.

This is a whole-class problem, not one function: every HTTP-backed method has it.

**Workaround in tree:** `pixel_map.read_map()` reissues the same GET with an explicit deadline rather than calling `getMapFunction()`. Only the map read is covered; no other HTTP-backed method is currently used.

**Upstream fix:** a constructor-level timeout with a sane default, threaded through every `requests` call.

### 2.3 `getPatternControls()` returns a shape its docstring denies (line 1288)

Documented as returning `{controlName: controlValue}`. Actually returns the raw websocket response:

```python
{"controls": {"<patternId>": {"sliderSpeed": 0.5, ...}}}
```

Storing that as-is buries the values a level deep under a device-specific pattern ID. Compare `getActiveControls()` (line 1272), which *does* unwrap to a flat dict — so the two sibling methods disagree on their return shape.

**Workaround in tree:** `controls.flatten_pattern_controls()` accepts both shapes, keyed by the requested ID or by the single key present.

**Upstream fix:** unwrap in `getPatternControls`, matching `getActiveControls`.

### 2.4 `PixelblazeEnumerator` cannot be stopped (lines 3453, 3478)

`_listen()` blocks in `recvfrom()` with no socket timeout:

```python
while self.isRunning:
    data, addr = self.listener.recvfrom(1024)
```

`stop()` sets `isRunning = False` and then `threadObj.join()` — but the thread is parked inside `recvfrom()` and will not re-check the flag until another beacon happens to arrive. On a quiet network that is a hang.

Also at line 3361: `devices = dict()` is a **class** attribute, so every enumerator instance shares one mutable device list.

**Workaround in tree:** `discovery.listen_for_beacons()` is a purpose-built listener — same packet format (`<LLL`, type 42, port 1889), with a socket timeout and no thread at all.

**Upstream fix:** `settimeout()` on the socket and loop on the flag; move `devices` into `__init__`.

### 2.5 `setMapFunction()` cannot express "no map" (line 1622)

```python
mapCoordinates = MiniRacer().call(mapFunction, self.getPixelCount())
```

The map is compiled locally: the JavaScript is executed against the device's pixel count to produce coordinates, which become the binary map data. There is therefore no way to ask for *no* map — an empty string is not a function and cannot be called.

That matters because clearing a map is a real operation, and clearing it properly means clearing the compiled `pixelmap.dat` too. Writing an empty `pixelmap.txt` alone leaves the compiled data in place and `render2D` keeps using coordinates from a map the device no longer reports.

Observed detail: a map cleared through the web UI reads back as **one whitespace character**, not an empty body. Any emptiness check has to treat whitespace-only as empty.

**Workaround in tree:** `pixel_map.write_map()` routes empty maps to `putFile('/pixelmap.txt', '\n')` plus `setMapData(bytes())`, and only uses `setMapFunction()` for real maps.

**Upstream fix:** accept an empty map function and clear both files.

## 3. Surprises that are not defects

Worth recording so nobody re-derives them.

### 3.1 `setControls` replaces the whole map

`setActiveControls()` sends `{"setControls": {...}, "save": bool}`, and the **device** replaces its stored control map rather than merging. Writing one control resets every other control on that pattern to uninitialised memory. Observed 2026-09-07 on `02 Frankensparker aftershock`: setting one input reset the other four.

This is device API behaviour, faithfully relayed — not a client bug. But it is a footgun the client could remove with a merging helper. Our `controls.write_controls()` does the read-merge-write.

### 3.2 There is no per-pattern control writer

`setActiveControls` targets whichever pattern is **running**. Setting another pattern's controls means activating it, writing, and putting back what was there. Again a device limitation, but it means "set this pattern's controls" is never a single call, and it briefly changes what the LEDs display.

### 3.3 `getConfigSettings()` is fast

It was assumed to be slow, because it waits for sequencer and expander packets as well. Measured at **~0.1 s** on both controllers. Caching its result per session is still reasonable, but not for performance.

### 3.4 `chipId` is only in the live response

`getConfig` reports an integer `chipId` — the immutable hardware ID, and the same value the UDP discovery beacon carries. It is **not** persisted in the `config.json` inside a `.pbb` backup, so a backup cannot tell you which device it came from. This was checked while trying to recover a device's ID while it was off the network; it could not be done.

### 3.5 `getActivePattern()` return type

The docstring says `str`, and firmware 3.67 does return a plain ID string. Our `pixelblaze_get_active_pattern` still defensively handles a `{id: name}` dict, from an earlier observation that was never pinned down — possibly an older firmware or an older client. **Low confidence; worth confirming and then simplifying** if the dict form cannot be reproduced.

### 3.6 `mini-racer` emits deprecation warnings on Python 3.14

Two `DeprecationWarning`s from `py_mini_racer/_dll.py` and `_objects.py` about `_pack_` on `ctypes.Structure`, "slated to become an error in Python 3.19". Harmless today; a future Python compatibility cliff in a transitive dependency, and one reason the heavyweight JS-engine dependency is worth noting. Only `setMapFunction` needs it.

## 4. Deciding what to do

Rough order of value if we do contribute upstream: 2.1 and 2.2 are the two that hang a caller with no diagnostic, and are cheap fixes. 2.3 is a small correctness fix. 2.4 matters only to users of the enumerator. 2.5 is the most invasive.

If upstream is unmaintained, the alternative is to keep the workarounds and add a short section to the workspace `CLAUDE.md` warning which client methods not to call directly — `getConfigExpander()` and `getMapFunction()` above all.

## 5. Verification

Every workaround has live coverage already, against PBLQ 0A4 H26-Barbie. If a version bump or fork switch happens, re-run:

- `pixelblaze_list_devices(check=True)` against both controllers, including one with an expander and one without — 2.1 regresses as a hang.
- `pixelblaze_get_pixel_map` and `pixelblaze_set_pixel_map` round trip, plus a clear, checking that the compiled map data goes too — 2.5.
- `pixelblaze_discover_devices` — 2.4.
- `pixelblaze_set_control` on a pattern with three or more controls, confirming the others survive — 3.1.
- The full `pytest` suite, which covers the shapes in 2.3 and the merge in 3.1 with fakes and needs no device.
