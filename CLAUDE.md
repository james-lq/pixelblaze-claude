# PixelBlaze AI Assistant Context

This workspace uses a PixelBlaze MCP server to develop LED patterns for one or more devices.

**Devices** live in `devices.toml` at the workspace root, keyed by each controller's immutable hardware chip ID. **Projects** live under `projects/<name>/`, each with its own `CLAUDE.md` describing that rig's pixel layout, coordinate system and design principles — loaded automatically when working in that directory.

## Using PixelBlaze MCP Tools

All `mcp_pixelblaze_*` tools are **deferred** and must be loaded via `tool_search` before they can be called. Skipping this step causes a cryptic `Cannot read properties of undefined (reading 'invoke')` error that looks like a network failure but isn't.

**Always do this first, before any PixelBlaze tool call:**
```
tool_search("pixelblaze list patterns")   // or whatever action is needed
```
Then call the tool returned by the search. This applies to every tool in the `mcp_pixelblaze_*` and `mcp_pixelblaze_docs_*` namespaces.

### Naming a device

Every tool that touches hardware takes a `device`. It accepts, in order:

1. a **chip ID** — `0x` plus 8 upper-case hex digits, e.g. `0x00AC056C`; this is the table key in `devices.toml` and the only durable identifier;
2. a **display name**, case-insensitive, e.g. `PB LQ 56C SENSOR` — a convenience that can go stale, since the name changes in the web UI in seconds;
3. an **IP address or dotted hostname** — either a registered device's address, or a one-off ad-hoc device that is used as given.

`pixelblaze_list_devices` shows what is registered; `pixelblaze_discover_devices` finds controllers on the LAN by their UDP beacons and adds any that are new.

Every connection to a registered device checks that the box answering at that address reports the expected chip ID, and **refuses to proceed on a mismatch** rather than deploying to the wrong controller after a DHCP reshuffle. A display-name mismatch only warns.

**`device` can be omitted** for a pattern that has been deployed before: it resolves to the device that pattern last went to, from its sidecar, then to the project's most recently used device. Naming a device a pattern has never been on deploys it there afresh, with its own new Pattern ID.

### Naming a project

Tools that create or list local files take a `project` — the folder name under `projects/` — or a `file_path`, which implies its project. `project.toml` in each folder sets that project's device-name prefix, ordinal policy, pixel map and preview-capture default; every key has a default, so the file can be absent entirely.

## macOS: Local Network Access

On macOS Ventura and later, each app must be explicitly granted permission to access local network devices. If the PixelBlaze is unreachable from VS Code or the terminal (connection refused, no route to host, or similar) but is accessible from a browser, this permission is the most likely cause.

**Fix:** Open **System Settings → Privacy & Security → Local Network** and enable access for **Visual Studio Code**. Then restart VS Code so the MCP server process inherits the updated permission.

## Device Crashes and Power Brownouts

LED current draw can exceed what the supply can deliver and reset the controller. This presents as a firmware or pattern bug and is not one, so rule it out before debugging code.

**Symptoms**

- The device resets repeatedly: `uptime` in the device statistics never accumulates, and the status LED flashes.
- Every strip goes dark at the same instant, including strips on different output expander channels.
- A bad enough brownout does not present as periodic resets at all — the device stops answering entirely (`Host is down`, connection timeouts) for tens of seconds at a time. **A Pixelblaze that has vanished from the network is a power suspect, not only a WiFi suspect** — see the macOS Local Network section above for the other main cause.
- Websocket operations that take several seconds fail mid-stream with `Connection to remote host was lost`. Preview capture is the usual casualty, since it streams ~150 frames over 6-8 seconds.

**Telling it apart from a pattern bug**

- `vmerr` stays `0` and `vmerrpc` stays `-1`: the VM is not faulting.
- Free memory (`mem`) stays flat: nothing is leaking.
- `rebootCounter` stays `0` while `uptime` keeps restarting: a hard reset, not a tracked reboot.
- **The decisive test:** lower the global brightness and re-run the identical pattern. Nothing about the code path changes, so if the fault disappears it is power. This isolates current draw from logic in one step and is worth doing early.

**Rules of thumb when designing patterns**

- White is the worst case: `hsv(h, 0, 1)` drives all three colour channels at roughly 60 mA per pixel (a common rule of thumb, but actual power draw is highly dependent on specific LEDs). A pattern that is mostly white costs far more than an equally bright single-hue one.
- Peak draw matters, not average. Effects that light many pixels at one instant — wide sweeps, simultaneous flashes, channels animating in lockstep — stack onto the same moment. Staggering channels in time spreads the load as well as usually looking better.
- **An output expander does not reduce current draw.** It parallelises data, not power, so adding channels adds load.
- Treat total lit pixels x brightness as a real budget, and re-check it whenever the pixel count grows.

**Alternative approach for power issues: LED power injection**
- Powering the LED strips independently from the controller can alleviate most power capacity / brownout problems.
- Key hardware requirement for this is that multiple power sources must have their common/ground planes cleanly tied together.

## Pattern Development Workflow

1. **Always call `docs_get_api_reference`** before writing new pattern code
2. Use `render2D(index, x, y)` for 2D layouts; `render(index)` for 1D strips
3. Use `beforeRender(delta)` for animation state updates
4. Export UI controls with `export var slider*` / `export var hue*` naming conventions
5. Test with `pixelblaze_create_pattern`, passing the `project` and a `device` — it auto-activates the new pattern
6. Iterate with `pixelblaze_update_pattern`, which finds the local file and its device from the pattern ID

### Pattern Thumbnails (Preview Images)

Every save (`create`, `update`, `deploy_local`) captures a live thumbnail from the running pattern the same way the web UI does: ~150 preview frames streamed from the device, gamma-corrected, resampled to 100 columns, and JPEG-encoded under ~5 KB. This adds roughly 6–8 seconds per save. If the pattern being saved is not the active one, it is activated for the capture and the previous pattern is restored afterwards.

- Set `preview_capture = false` in a project's `project.toml` to skip capture and store a neutral placeholder thumbnail instead. Pass `capture_preview=False` to a single call to override it either way — worth doing on fast edit loops.
- Use `pixelblaze_regenerate_preview(pattern_id)` to backfill a thumbnail for a pattern already on the device.
- Patterns saved with **no** thumbnail make the web UI's pattern list stall and show the "Pixelblaze is having trouble loading preview images" dialog; the placeholder exists so that can't happen.

### Pattern File Naming Convention

Pattern files live in a project's `patterns/` folder and use a 2-digit ordinal prefix, spaces, and natural capitalization:

```
projects/H26-Finale/
  project.toml
  patterns/
    NN Name With Spaces.js              ← pattern code
    NN Name With Spaces.sidecar.toml    ← where it has been deployed, and with what
    NN Name With Spaces.mapper.js       ← pixel map for that pattern (if 2D/3D)
```

The three files are matched **by filename stem**. Renaming a pattern means renaming all of them together; nothing goes looking for orphans.

**The local filename and the device display name are different.** A project's `pattern_name_prefix` — defaulting to the folder name — is added on the way to the device so a project's patterns cluster together in the Pixelblaze pattern list:

```
local file:    patterns/03 Spark Chorus.js
device name:   H26-Finale 03 Spark Chorus
               ^^^^^^^^^^ pattern_name_prefix
```

The prefix never appears in the local filename; the project folder already groups files locally. Set `pattern_name_prefix = ""` to deploy under bare filenames. The prefix is joined with a single space, so there is no separator to configure — don't write one into the value.

**Ordinals are optional per project.** `ordinals = "auto"` (the default) prepends the next free `NN ` to a new pattern whose name lacks one, which makes the web UI's alphabetical sort useful. `ordinals = "none"` leaves names alone. An explicit ordinal is always kept either way.

Filenames must be unique within a project and legal on Windows, macOS and Linux.

### Pattern File Header

Every pattern JS file starts with a single-line comment naming the pattern, and nothing else:

```js
// NN Name With Spaces
```

The name here matches the filename stem. It is worth the one line because a pattern downloaded off a device would otherwise lose its name on the way to disk.

Pattern IDs are **not** in the file. A pattern deployed to two devices has two IDs, one minted per device, so a single header line could never describe it; the IDs live in the sidecar instead.

Follow the header line with a comment block containing:
1. **Effect description** — what the pattern looks like, in plain language
2. **Design notes** — key implementation decisions, algorithms used, and gotchas

### Pattern Sidecar Files

`patterns/<stem>.sidecar.toml` records where a pattern has been deployed. It is written by the tooling on every deploy, committed to git, and safe to read or hand-edit.

```toml
# Written by the pixelblaze-mcp tooling on every deploy. Most recent device first.

[[deployment_history]]
device_id = "0x00AC056C"
device_name = "PB LQ 56C SENSOR" # a hint, not used for matching
pattern_id = "mSXJ5etzaarWuZSPv"
deployed_at = 2026-09-08T02:59:12Z
deployed_hash = "1e7d7a1f"

[deployment_history.controls]
sliderCycleSeconds = 0.42
```

- One entry **per device**, most recent first. Redeploying to a device already listed updates its entry in place and moves it to the front. It is not a log of every deploy — `git log` on the sidecar is the log.
- **The front entry is the pattern's current device**, which is what a redeploy with no `device` argument targets.
- `device_id` is the durable link to `devices.toml`; `device_name` is a human hint expected to drift.
- `deployed_hash` covers the file as sent to the device. Whether the local file has been edited since is **computed** by re-hashing, never stored.
- `controls` holds the values live on that device, read back after each deploy so tuning done in the web UI is captured rather than clobbered. Values keep their own types: floats for sliders, booleans for toggles, three-float arrays for colour pickers.
- A `.js` with no sidecar is simply "never deployed".
- If a pattern has since been deleted from a device, its entry stays; the next deploy notices the ID is gone and creates it afresh.

### 2D Patterns: Never Export Both `render` and `render2D`

If a pattern exports both `render(index)` and `render2D(index, x, y)`, PixelBlaze will use the 1D renderer **even when a pixel map is configured**. For 2D mapped patterns, only define `render2D` — omit or comment out `render` entirely.

### Slider Comments
Every slider function should have a comment on the line above describing what the control does in plain language, as if explaining to a user. Maximum 1 sentence.

Example:
```js
// How fast the animation cycles
export function sliderSpeed(v) { speed = mix(0.01, 0.06, v) }
// How many raindrops fall at once
export function sliderDropRate(v) { dropRate = mix(2, 20, v) }
// How wide each ball is stretched along the LED strips
export function sliderWidth(v) { xSize = mix(0.08, 0.5, v) }
// Number of balls bouncing simultaneously (1-5)
export function sliderBalls(v) { numBalls = floor(mix(1, 5.99, v)) }
```

## TODO.md Convention

`TODO.md` is a list of open items only. When an item is completed, delete it; do not tick it off, annotate it as done, or keep a log of finished work (git history serves that purpose). Items are plain bullets, not checkboxes.
