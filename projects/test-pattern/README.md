# test-pattern

Basic functionality testing against the current Pixelblaze device. See `CLAUDE.md` for the working summary.

## Device snapshot (2026-09-05)

Queried directly via `pixelblaze-client` from the workspace `.venv`.

### `getConfigSettings()`

```json
{
  "name": "Pixelblaze_047B0E",
  "brandName": "",
  "pixelCount": 250,
  "brightness": 1,
  "maxBrightness": 100,
  "colorOrder": "GRB",
  "dataSpeed": 3500000,
  "ledType": 2,
  "sequenceTimer": 15,
  "transitionDuration": 0,
  "savePatternOnButton": false,
  "sequencerMode": 0,
  "runSequencer": false,
  "simpleUiMode": false,
  "learningUiMode": false,
  "discoveryEnable": true,
  "remoteServer": "",
  "timezone": "",
  "autoOffEnable": false,
  "autoOffStart": "00:00",
  "autoOffEnd": "00:00",
  "cpuSpeed": 240,
  "networkPowerSave": false,
  "mapperFit": 0,
  "leaderId": 0,
  "leaderGoneTimeout": 0,
  "nodeId": 0,
  "soundSrc": 0,
  "accelSrc": 0,
  "lightSrc": 0,
  "analogSrc": 0,
  "exp": 0,
  "ver": "3.67",
  "chipId": 293646,
  "boardType": "pb32"
}
```

### Active pattern

- `fast pulse 2D/3D` (id `BvZoMSk6wu37yZ8zY`), a stock Pixelblaze example. No exported controls.

### Patterns on device

49 patterns: the stock example set plus a handful of user patterns carried over from earlier work (`AAA QN25 Perspective Magick`, `QN26 FishyKITT`, `_QN26 - SIREN TEST`, `Coronal Mass Ejection PXLBLZ remix`, `Newfire`).

### Notes

- `getPatternSourceCode()` returns the source wrapped as a JSON string `{"main": "..."}`, confirming the item in the root `TODO.md`.
- No pixel map is configured on the device.

## Functionality test log

### 2026-09-05: first end-to-end MCP round-trip

Ran against `Pixelblaze_047B0E` through the Claude Code MCP server after pointing `.env` at the new device.

| Tool | Result |
|---|---|
| `pixelblaze_get_device_info` | Pass after fix (pixel_count was always null) |
| `pixelblaze_get_active_pattern` | Pass |
| `pixelblaze_list_patterns` | Pass |
| `pixelblaze_list_local_patterns` | Pass |
| `pixelblaze_get_controls` | Pass after two fixes (see below) |
| `pixelblaze_create_pattern` | Pass; local filename does not follow convention (see below) |
| `pixelblaze_update_pattern` | Pass on device; created a duplicate local file (see below) |
| `pixelblaze_get_pattern_code` | Pass, but returns the `{"main": ...}` envelope (known, see root TODO) |
| `pixelblaze_set_control` | Pass after fix (called a nonexistent client method) |
| `pixelblaze_set_brightness` | Pass |
| `pixelblaze_set_active_pattern` | Pass |
| `pixelblaze_delete_pattern` | Pass |

Test pattern: `01 TEST Chaser` (device ID `MBCPgrMezMKxXbvZL`, since deleted from the device). The local file in `patterns/` is kept as a reusable smoke test; redeploying it will assign a new ID.

Fixes applied to `src/pixelblaze_mcp/pixelblaze_tools.py` during this run: `get_controls` now uses `getActiveControls()` (live values) instead of treating `getActivePattern()` as a dict and reading only flash-saved values; `set_control` now calls `setActiveControls({name: value})`; `get_device_info` reads pixel count from config settings.

Tooling gaps observed (tracked in root `TODO.md`):

- The tooling only recognises a pattern's ID from a first-line header of the exact form `// <Name> — Pattern ID: <id>` (em dash). A block-comment header is ignored, so `update_pattern` cannot find the local file and writes a second one.
- `create_pattern` names the local file `NN-slugified-name.js`, which conflicts with the `NN Name With Spaces.js` convention in the root `CLAUDE.md`, and prepends a fresh ordinal even when the display name already has one (`01-01-test-chaser.js`).

### 2026-09-05: rename and relabel controls

Renamed to `01 TEST RGB 1D Chaser Cycle`; period input is now `inputNumberSecondsPerColor`, width slider is `sliderWidthPercentOfPixelCount`. Pixelblaze derives control labels from the function name by splitting CamelCase, so punctuation cannot appear in a label.

Observations:

- `pixelblaze_deploy_local_pattern` took the name from the device rather than the local header, so a local rename did not propagate. Fixed: the local header name is now the source of truth on redeploy.
- When a pattern's set of controls changes, Pixelblaze appears to reapply previously saved control values **by position, not by name**. After the relabel, the old width value (0.555) showed up on the new first control (seconds per colour) until the controls were re-saved. After changing control names, re-set and save the values.

### 2026-09-05: live thumbnail capture

Root cause of the "trouble loading preview images" dialog was the tooling saving every pattern with an empty preview image; the pattern list waits 10 s for each missing thumbnail. Fixed by capturing a real thumbnail on every save (`src/pixelblaze_mcp/preview.py`), matching the web UI's method, with a placeholder as the first-save/fallback image and a `PIXELBLAZE_PREVIEW_CAPTURE=0` toggle. Measured: ~6 s capture, ~8 s total deploy. Added `pixelblaze_regenerate_preview` for backfilling. New dependency: Pillow.
