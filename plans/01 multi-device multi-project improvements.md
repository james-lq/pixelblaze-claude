# Plan 01 — Multi-device, multi-project workflow improvements

Status: Nothing here is implemented yet. Open questions are collected in section 8; decisions get folded back into the relevant section once made.

Related open items in the root `TODO.md`: *Device configuration* (both items), *Pattern naming and metadata* (both items), and the *Controls and deployment* sidecar item. This plan absorbs those; the *Code sharing* and *MCP tooling* sections stay in `TODO.md` but are referenced where they constrain the design.

Changes from draft 3: TOML and `.sidecar.toml` confirmed; `slug` becomes `pattern_name_prefix`, defaulting to the folder name with an empty string allowed; config examples comment out every token that has a well-defined default; the device ID question is settled against a live device and the initial registry entry is written down; the deployment history cap is removed.

## 0. Notes for the implementing session

This plan is meant to be picked up cold. Read, in order: the root `CLAUDE.md` (tool-loading quirk, file conventions), this plan, then `src/pixelblaze_mcp/config.py`, `pattern_file.py`, and `pixelblaze_tools.py` (about 700 lines total; `server.py` just registers tools).

Working constraints:

- **Never commit without being asked.** Make changes in the working tree and stop.
- **Do not modify, rename, or delete any pattern that already exists on `10.0.1.106`.** Smoke tests go through the `test-pattern` project, creating new throwaway patterns and deleting only those. The device is carrying a pixel map; do not push a map to it until section 5 is being implemented and the map has been downloaded first.
- **MCP server code changes need the server restarted** (`/mcp` in Claude Code) before the tools reflect them. This is the ordinary edit loop and is not the restart problem this plan removes; that one is about *configuration* changes.
- `.venv` is Python 3.14; `pyproject.toml` requires 3.11+. `tomlkit` and `pytest` are the only new dependencies (section 10). Add them with `uv add` / `uv add --dev`.
- There are no tests today. Section 10 says what to add; do it alongside each phase rather than at the end.
- Workspace root is the directory containing `devices.toml` (today it is found as `Path(__file__).parent.parent.parent` in `config.py`; keep that). Relative `file_path` arguments resolve from there, replacing the current `PATTERNS_DIR.parent.parent` hack.

## 1. Where things stand today

A quick audit of the current tooling, so the plan is grounded in what actually has to change.

- **Device and project are baked in at import time.** `src/pixelblaze_mcp/config.py` calls `load_dotenv()` and reads `PIXELBLAZE_HOST` and `PROJECT_FOLDER` into module-level constants (`PIXELBLAZE_HOST`, `PROJECT_FOLDER`, `PATTERNS_DIR`). It raises if the host is missing, so the server will not even start without a `.env`. `pattern_file.py` and `pixelblaze_tools.py` import `PATTERNS_DIR` directly, and `server.py` embeds the host in the FastMCP `instructions` string and the `pixelblaze://device` resource. Every one of those is a reason a change needs a server restart.
- **Every device tool implicitly targets the one host.** The `_pb()` context manager constructs `Pixelblaze(PIXELBLAZE_HOST)`. No tool takes a device argument.
- **Pattern identity is single-device.** The header line `// NN Name — Pattern ID: abc123` carries exactly one ID, and `find_local_pattern_file()` locates a file by grepping for it. Pattern IDs are minted per device (`pb.makeId()`), so the same pattern deployed to two devices has two IDs and the header can only hold one. This is the single biggest structural obstacle to multi-device support.
- **Deploy metadata lives inside the source file.** The trailing `// ---- pixelblaze-mcp metadata----` block holds `@deployed`, `@deployed-hash`, and `@modified-since-deployed`. The last is redundant: `parse_pattern_file()` already recomputes it from the hash. `TODO.md` and `CLAUDE.md` both already call this an anti-pattern.
- **Pixel maps have two competing conventions and no tooling.** `project-sound-level-meter` uses per-pattern `NN Name.mapper.js`; `project-daft26-turtle-curtain` uses a project-level `pixel-map.js`. Neither is touched by the MCP server; maps are pasted into the web UI by hand. A Pixelblaze holds **one** map per device, not one per pattern, so the per-pattern convention slightly misrepresents the hardware model. `pixelblaze-client` exposes `getMapFunction()` / `setMapFunction()`, so tooling support is cheap.
- **Device facts are scattered into prose.** The frankensparker `CLAUDE.md` hard-codes the device name, IP, and firmware version. That is exactly the information the device registry should own.
- **Ordinals are mandatory today.** `canonical_pattern_name()` always prepends the next free `NN ` with no way to turn it off, and there is no notion of a project-level name prefix.
- **Offline mode is a root-level flag file** (`.pixelblaze_offline`), global to the workspace rather than per device.
- **Small inconsistencies to sweep up while in here:** `README.md` says `.mcp.json` is gitignored but it is committed (the ignore line is commented out); two projects still have legacy `NN-name.js` filenames; `README.md` documents `PATTERNS_DIR` which no longer exists.

Useful `pixelblaze-client` capabilities not yet used, which the plan leans on: `getConfigSettings()` (which carries the hardware ID, see 3.1), `getDeviceName()`, `getConfigExpander()`, `getPatternControls(id)`, `setActiveControls(dict, saveToFlash=...)`, `getMapFunction()` / `setMapFunction()`, and the UDP beacon enumerator for address discovery.

## 2. Goals and non-goals

Goals:

1. No server restart, ever, to change device or project. Configuration is read at call time.
2. A committed **device registry** at the workspace root, keyed by immutable hardware ID, readable by humans and maintainable by tooling.
3. Deploying a pattern to a device is one explicit argument. Re-deploying to the device it last went to needs no argument at all.
4. A **per-pattern sidecar** recording where a pattern has been deployed, with the control values that were live there, replacing the in-file metadata block.
5. One coherent convention for **pixel map files** that the tooling can actually deploy.
6. Files that are easy for a human to scan and occasionally edit, but that are mostly managed through Claude and the MCP tooling, with comments surviving tool edits.

Non-goals for this plan (tracked elsewhere): the code-sharing / include mechanism, bulk pattern download, and the control-value merge bug fix in `pixelblaze_set_control` (though section 6 sets up where merged values are recorded).

## 3. Proposed layout

```
pixelblaze-claude/
  devices.toml                       # workspace device registry (committed)
  projects/
    H26-Finale/                      # project identity is the folder name
      project.toml                   # project manifest: name prefix, ordinals, map, preview
      pixel-map.js                   # optional project-level pixel map
      CLAUDE.md
      patterns/
        02 Frankensparker aftershock.js               # pattern source, no metadata block
        02 Frankensparker aftershock.sidecar.toml     # deployment history + controls
        02 Frankensparker aftershock.mapper.js        # optional per-pattern map override
```

All three config files are TOML, read and written with `tomlkit` so that comments and formatting survive tool edits (8.1 has the reasoning). Convention for every example below, and for the files the tooling writes: **a token with a well-defined default is present but commented out, showing that default**, with any explanation on the line(s) above it, so a human enables an override by deleting one `#`.

### 3.1 Device registry: `devices.toml`

Keyed by the device's immutable hardware ID, with the display name as the first field so the file scans by eye. Tool-maintainable: `discover_devices` and `list_devices` may add entries and refresh `name` / `host`. `notes` is human-owned and never touched by tooling; it is a TOML multi-line basic string whose content is **Markdown by convention**, so it stays easy to read and to update by hand or through Claude, and can carry lists, emphasis, and links to project docs. Tools that display a registry entry print it verbatim.

This is the intended initial content, taken from the device that was reachable at the time of writing (read-only; nothing on it was changed). The second device is listed as a stub until it is back on the network and `discover_devices` can fill in its ID.

```toml
# Pixelblaze device registry. Table keys are the hardware chip ID (from getConfig's
# `chipId`, and the same value the UDP discovery beacon sends), written as 8 lower-case
# hex digits. `name` and `host` are refreshed by the tooling. `notes` is yours: a
# multi-line string, Markdown by convention, never touched by tooling.

[devices.00ac00a4]
name = "PB LQ 0A4 SENSOR"
host = "10.0.1.106"
notes = """
Pixelblaze v3 (pb32), firmware 3.67, **sensor board**, no output expander.

- 50 px, GRB
- Carrying a 698-char pixel map and 46 patterns (mostly Electromage examples) as of 2026-09-08
"""

# ID unknown until the device is reachable; run pixelblaze_discover_devices to fill it in.
# [devices.TODO]
# name = "PB LQ 56C SENSOR"
# host = "10.0.1.107"
```

Identity, weakest to strongest:

- **`host`** is only how the tooling reaches the device. DHCP can reassign it.
- **`name`** is the device's own configured display name. It is echoed everywhere a human reads output (tool results, `list_local_patterns`, sidecars) so associations are easy to make at a glance, but it changes in the web UI in two seconds, so tooling treats it purely as a **hint**: a mismatch between registry and device produces a warning, never an error. Only `list_devices(check=True)` and `discover_devices` write the refreshed value back; an ordinary tool call never writes `devices.toml`, so a deploy does not produce a surprise diff in the registry.
- **The table key** is the immutable hardware ID. Every connection verifies the device at `host` reports this ID and **refuses to proceed** on a mismatch. This is the guard against deploying to the wrong box after a DHCP reshuffle.

**Referring to a device in a tool call.** The `device` argument accepts, in this order: an exact hardware ID; a display name, case-insensitive; a literal IP or hostname (an **ad-hoc device**, used directly with no verification, for one-off "try it on this other box"). A display name that matches more than one entry is an error that lists the IDs. Names are resolved to IDs at call time, so a renamed device only breaks the human's habit, never the sidecar records.

**Where the ID comes from, confirmed against the live device.** The `getConfig` websocket response includes an integer `chipId`. On the device above it is `11272356`, which is `0x00ac00a4`, and the UDP discovery beacon on port 1889 (three little-endian `uint32`s: header `42`, sender ID, sender clock) carried exactly the same value. So:

- Verification on connect is one `getConfigSettings()` call and a comparison; no beacon listening needed. That call is slowish (it waits for the sequencer and expander packets too), so the verified `host -> id` pairing is cached for the life of the MCP process and checked once per device per session.
- The ID is formatted as 8 lower-case hex digits, zero-padded, no `0x`. Bare TOML keys may be composed of letters and digits, including all digits, so no quoting is needed. Tooling accepts the decimal form as input and always writes the hex form.
- The default `Pixelblaze_XXXXXX` device name uses the low bits of the same ID, which is also where the `0A4` in this device's name came from. That is a handy human cue but the tooling never relies on it.

Planned optional fields, added when needed rather than now: `[devices.<id>.hardware]` with `sensor_board`, `output_expander`, `expander_channels`; `pixel_count` as a sanity check rather than a source of truth. `getConfig` already reports `boardType`, `ver`, `pixelCount`, `ledType`, `colorOrder`, and the expander config, so `list_devices --check` can print all of that without any of it being stored.

### 3.2 Project manifest: `projects/<name>/project.toml`

Human-authored, committed. Nothing in it is tool-written today, but it goes through `tomlkit` like everything else so that can change later without a format migration. Every token has a default, so a valid manifest can be empty or absent.

```toml
# Prefix for the on-device display name so a project's patterns group together
# in the Pixelblaze pattern list. Local filenames never carry it. Defaults to the
# project folder name; set to "" to deploy patterns under their bare filenames.
#pattern_name_prefix = "H26-Finale"

# "auto" prepends the next free two-digit ordinal (`NN `) to a new pattern's name
# when it lacks one, which makes the web UI's alphabetical sort useful.
# "none" leaves names alone. An explicit ordinal in a name is always kept.
#ordinals = "auto"

# Project-level pixel map, relative to this folder, pushed to the device on deploy
# when it differs from what is there. A per-pattern `<stem>.mapper.js` overrides it.
#pixel_map = "pixel-map.js"

# Capture a live thumbnail on every save (adds 6-8 s). Per-call `capture_preview`
# overrides this.
#preview_capture = true
```

The project's identity is its folder name under `projects/`; the manifest does not repeat it. Tools accept the folder name as the `project` argument.

**No `default_device`.** The sidecar's deployment history already answers "where did this last go" per pattern, and for a brand-new pattern the project's most recently used device (across all its sidecars) is a better guess than a manifest field that would go stale. The full resolution chain is in 4.1. If that heuristic proves annoying in practice, `default_device = "<id or name>"` is the name to add.

### 3.3 Pattern sidecar: `patterns/<stem>.sidecar.toml`

Tool-written, human-editable, committed. One file per pattern, named by the pattern's filename stem.

```toml
# Written by the pixelblaze-mcp tooling on every deploy. Most recent device first.

[[deployment_history]]
device_id = "00ac00a4"
# Display name at deploy time; a hint for humans, not used for matching.
device_name = "PB LQ 0A4 SENSOR"
pattern_id = "mSXJ5etzaarWuZSPv"
deployed_at = 2026-09-08T01:12:40Z
deployed_hash = "a2b066c7"
# Hash of the pixel map on the device at deploy time. Absent when no map was involved.
map_hash = "d41d8cd9"

# Control values live on that device, read back after each deploy.
[deployment_history.controls]
sliderCycleSeconds = 0.42
sliderSparkWidthFractionOfStrip = 0.1
sliderChannelSync = 0.0

[[deployment_history]]
device_id = "9f8e7d6c"
device_name = "PB bench spare"
pattern_id = "Q2n8sLk1xvC0pRt7Z"
deployed_at = 2026-09-02T22:05:11Z
deployed_hash = "5c1e90aa"

[deployment_history.controls]
sliderCycleSeconds = 0.5
```

Semantics:

- `deployment_history` is a **per-device** list, most recent first, one entry per device the pattern has ever been deployed to. Redeploying to a device already in the list updates that entry in place and moves it to the front. There is no cap: typical use is one or two devices, and a list that grows is not a problem worth code. It is deliberately not a log of every deploy; `git log` on the sidecar is the log.
- **The front entry is the pattern's current device.** That is what "redeploy" means with no `device` argument.
- `device_id` is the durable link to the registry. `device_name` is the human hint and is expected to drift.
- `pattern_id` is the ID on that device. This replaces the header line's single ID. If the pattern has since been deleted from the device, the entry stays; a redeploy to that device notices the ID is gone, creates the pattern afresh, and updates the entry.
- `deployed_at` (a native TOML offset datetime, UTC), `deployed_hash`: as today, i.e. the first 8 hex characters of SHA-256 over the file content as sent to the device (header line included, trailing whitespace stripped). `modified-since-deployed` is not stored; it is computed by comparing the current file hash with the front entry's `deployed_hash`, as `parse_pattern_file()` already does. `map_hash` uses the same scheme over the map source text.
- `map_hash`: hash of the pixel map on the device at deploy time (section 5). Lets the tooling notice a pattern was deployed against a different map than the one now declared.
- `controls`: the control values live on that device, captured after each deploy and by `snapshot_controls`. The front entry's controls double as the defaults: a first deploy to a new device seeds from them, and a redeploy to a known device leaves the device's own stored values alone (section 6). **Values are not all floats.** The device's own control store (`/p/<id>.c`, visible in the `.pbb` backup) holds sliders as floats, toggles as booleans, and colour pickers as arrays of three floats, e.g. `hsvPickerCrystal = [0.727, 0.683, 0.718]`. The sidecar stores them as the corresponding TOML types, and the tooling must not coerce.
- **Renaming a pattern file** means renaming its sidecar (and any `.mapper.js`) with it; the tooling matches the three by stem and does not go looking for orphans. A `.js` with no sidecar is simply "never deployed".

Once the sidecar exists, the header line simplifies to `// NN Name With Spaces` (name only). The tooling matches file to device pattern via the sidecar, falling back to display name. Keeping the name in the header is still useful because `pixelblaze_get_pattern_code` on a downloaded pattern otherwise loses it.

Hash note for the future code-sharing work: when includes arrive, the sidecar should grow `source_hash` (the file as edited) alongside `deployed_hash` (the expanded code sent to the device). Naming `deployed_hash` now keeps that door open.

### 3.4 Pattern naming convention

Recommendation: fold the naming change into phase 1. The only code involved is `canonical_pattern_name()` / `new_pattern_file_path()` in `pattern_file.py`, which phase 1 has to touch anyway to make them project-aware, and the device-name-to-file matching rule is rewritten in phase 2 regardless.

```
local file:    patterns/03 Spark Chorus.js
device name:   H26-Finale 03 Spark Chorus
               ^^^^^^^^^^ pattern_name_prefix   ^^ optional ordinal
```

- **`pattern_name_prefix`** defaults to the project folder name and can be overridden in `project.toml`. It is joined to the rest of the name with a single space, so there is no separator to configure. Filename-safe characters only (the tooling validates), since the device name has to map back to a filename. An **empty string** means no prefix at all: patterns deploy under their bare filenames, exactly as today.
- **The prefix goes on the device name only, never the local filename.** The project folder already groups files locally. The invariant "filename stem == device display name" becomes "device display name == `<prefix> <filename stem>`", still a pure function in both directions.
- **Ordinals stay, and become optional.** `ordinals = "auto"` (default) keeps today's behaviour of prepending the next free `NN ` when a name lacks one. `"none"` turns the auto-prepend off. An explicit ordinal in a name is always respected either way.
- The prefix sorts before the ordinal so a project's patterns cluster together on the device, then order by ordinal within the cluster.

Consequences:

- **Matching device patterns to files** is by sidecar `pattern_id` first (phase 2). Name matching is the fallback and strips the project's prefix before comparing to the filename stem. Device patterns carrying a prefix no project declares are "not ours", which is the right answer for hand-made or downloaded patterns.
- **Changing the prefix** renames every pattern on the device on its next deploy, because the local name is already the source of truth on redeploy. `list_local_patterns` reports "device name differs" for patterns not yet redeployed. `deploy_project` (4.3) makes a prefix change a one-call operation.
- **Legacy names on the device** (the `AAA H24 - ...` style) are unaffected.
- **Name length** on the device is undocumented, but the reachable device already carries a 37-character name (`Example: ui controls (lightning ZAP!)`) without trouble, and `H26-Finale 03 Spark Chorus` is 26. Not a practical concern.

## 4. MCP tool changes

### 4.1 Configuration resolution

Replace the import-time constants in `config.py` with call-time resolvers. All three files are tiny; reading them on every call is cheaper than any cache-invalidation story and is what makes restarts unnecessary.

- `load_devices() -> Registry` parses `devices.toml` with `tomlkit`, validates with pydantic (already a transitive dependency via `mcp`) so a typo in a field name is a clear error rather than a silent default.
- `load_project(name) -> Project` parses `projects/<name>/project.toml` and resolves `patterns/`, `pixel_map`, prefix, and defaults.
- `resolve_device(arg, *, sidecar=None, project=None) -> Device` with this precedence:
  1. explicit `device` argument (ID, name, or ad-hoc host);
  2. the front entry of the pattern's sidecar `deployment_history`;
  3. the most recent `deployed_at` across all sidecars in the project;
  4. error listing the registered devices.

Delete `PIXELBLAZE_HOST` / `PROJECT_FOLDER` handling and the import-time `EnvironmentError`. `PIXELBLAZE_PREVIEW_CAPTURE` moves to `project.toml` with a per-call `capture_preview` override; `.env` is then unused and `python-dotenv` is dropped. `tomlkit` is added.

`server.py`: the `instructions` string stops naming a host and instead explains the registry and the `device` / `project` parameters. The `pixelblaze://device` resource becomes `pixelblaze://devices` and renders the registry.

### 4.2 Parameters on existing tools

Add optional parameters rather than new tools wherever possible; optional parameters are backward compatible with how the tools are called today.

| Tool | New parameters | Resolution when omitted |
|---|---|---|
| `pixelblaze_list_patterns`, `get_active_pattern`, `set_active_pattern`, `get_pattern_code`, `delete_pattern`, `get_controls`, `set_control`, `get_device_info`, `set_brightness`, `regenerate_preview` | `device` | error listing registered devices (no pattern or project context to infer from) |
| `pixelblaze_create_pattern` | `project`, `device`, `capture_preview` | `project` required; `device` via chain step 3 |
| `pixelblaze_update_pattern` | `device`, `capture_preview` | project and device inferred by locating the sidecar holding this `pattern_id` |
| `pixelblaze_deploy_local_pattern` | `device`, `capture_preview` | project from `file_path`; device via chain step 2 |
| `pixelblaze_list_local_patterns` | `project` | omit to list every project, grouped |

Behaviours worth stating so they are not left to guesswork:

- **An explicit `device` with no sidecar entry always creates a new pattern on that device** (fresh ID, new history entry moved to the front). It never updates a pattern on some other device.
- `pixelblaze_delete_pattern(pattern_id, device)` removes the pattern from the device and **leaves the sidecar untouched**. The device is the source of truth for what is deployed; the sidecar is a record of where things went, and a stale entry costs nothing (the next deploy to that device simply finds no pattern under the recorded ID and mints a new one, updating the entry in place). No tool ever deletes a local `.js` or sidecar.
- `pixelblaze_set_control(name, value)` must accept a float, a boolean, or a list of three floats, matching what the device stores (3.3). Today's signature is `float` only.
- In offline mode, `create_pattern` writes the `.js` and no sidecar (phase 2) or a `(pending)` header (phase 1); `list_local_patterns` reports it as never deployed; `deploy_local_pattern` does the first deploy.
- **Phase 1 file lookup by pattern ID.** Today `find_local_pattern_file(pattern_id)` greps the header line of every `.js` in one folder, `PATTERNS_DIR`, which `.env` pinned to a single project. Phase 1 removes that pin, but the sidecar that would map an ID to a file does not exist until phase 2, and `update_pattern(pattern_id, code)` receives nothing that identifies a project. So for the duration of phase 1 the same grep runs over `projects/*/patterns/*.js`, every project's folder. It is cheap (a few dozen small files) and unambiguous (IDs are 17 random characters minted per device, so collisions do not happen in practice). Phase 2 replaces it with the equivalent scan over `*.sidecar.toml`, which is the same shape with the ID in a different file.

Design rule: **file paths are the primary handle for local-side operations; pattern IDs for device-side ones.** A file path implies its project. A pattern ID is globally unique in practice (random per device), so scanning every `projects/*/patterns/*.sidecar.toml` for it is cheap and reliable for `update_pattern`, and the entry it is found in names the device.

### 4.3 New tools

- `pixelblaze_list_devices(check=False)` renders `devices.toml`; with `check=True` it connects to each, reports the live ID, name, board, firmware, pixel count and expander config next to the registry values, flags ID mismatches, and refreshes `name` / `host` in the file (comments preserved).
- `pixelblaze_discover_devices(dry_run=False)` listens for LAN beacons to collect addresses, connects to each for `chipId` and name, and adds any unknown device to `devices.toml` with `name` and `host` filled in and an empty `notes`. Reports what it added or would add.
- `pixelblaze_deploy_project(project, device=None, only_modified=True)` deploys every pattern in a project to one device. This is the "move a whole project to another box" and "prefix change" operation. Sequential inside the tool, since MCP calls cannot be parallelised safely.
- Pixel map tools, section 5. Control tools, section 6.

### 4.4 Session defaults (optional nicety, later)

Nothing above needs persisted state. If passing `device=` turns out to be noisy in practice, an **in-memory** `pixelblaze_use(project=..., device=...)` that sets process-lifetime defaults is a small addition, and being memory-only it cannot recreate the restart problem. Defer until the per-call form has been lived with.

## 5. Pixel maps

Unify the two existing conventions around the hardware model (one map per device):

- `project.toml` `pixel_map` names a project-level map file (the `daft26` convention).
- A per-pattern `<stem>.mapper.js` (the `sound-level-meter` convention) overrides it for that pattern. Kept because a project can legitimately mix 1D and 2D patterns, and because it already exists.
- Deploying a pattern compares the hash of the resolved map (per-pattern → project → none) with `getMapFunction()` on the target device. If they differ, the tool pushes the map with `setMapFunction()` and records `map_hash` in the sidecar entry. A `deploy_map=False` argument skips the push for cases where the device map is managed by hand.
- New tools: `pixelblaze_get_pixel_map(device, file=None)` (download, the reverse direction) and `pixelblaze_set_pixel_map(device, file)` for explicit control.

This closes the "stale map from another project left on the device" failure recorded in the frankensparker `CLAUDE.md`, because a project with no map declared deploys with an explicit empty map. Note that the newly registered device is currently carrying a map, so the first deploy of a map-less project to it will clear that map; `deploy_map=False` or `get_pixel_map` first if it is worth keeping.

The `TODO.md` question of whether the include mechanism should also cover `.mapper.js` files stays open; nothing here prevents it.

## 6. Control values

Built entirely on the sidecar's per-device `controls`. The rules:

1. **First deploy to a device** (no entry for it yet): after the save, push the front entry's `controls`, if any, with `setActiveControls(..., saveToFlash=True)`. This is the "defaults" behaviour and addresses the uninitialised-garbage TODO item without a separate defaults field. Needs the `TODO.md` verification about whether exported `var` initialisers are honoured; the sidecar approach works regardless of the answer.
2. **Redeploy to a known device**: leave the device's stored values alone (confirmed from the `.pbb` backup: the device keeps them in a separate `/p/<id>.c` file next to the pattern binary, so a code save does not touch them), then **read them back** into that entry's `controls`. Every deploy therefore refreshes the sidecar, and tuning done in the web UI since the last deploy is captured rather than clobbered. A `controls="push"` argument forces the sidecar values onto the device instead, for the restore-after-reflash case.
3. `pixelblaze_snapshot_controls(file_path, device=None)` does the read-back on demand, without a deploy. `pixelblaze_restore_controls(file_path, device=None)` does the push on demand.

The `set_control` merge bug is fixed independently; once fixed, `pixelblaze_set_control` also updates the matching sidecar entry so the committed record tracks what was actually set.

## 7. Migration

Done as its own commit, per `TODO.md`. A script `scripts/migrate_layout.py` that takes a project name and is safe to run more than once (a file already migrated is skipped), so projects can be migrated as their device IDs become known; delete the script once every project is through. Plus some `git mv`:

1. `git mv project-<x> projects/<X>` for each project. Proposed names: `H26-Finale` (from `project-h26-frankensparker`), and the rest with the `project-` prefix dropped: `daft26-turtle-curtain`, `fishy-sword-pulse`, `layered-acrylic`, `sound-level-meter`, `test-pattern`. Rename anything else at the same time if wanted; the names are not load-bearing.
2. Create `devices.toml` with the content in 3.1. The `10.0.1.107` device's ID is filled in by `discover_devices` once it is reachable.
3. For each pattern file in a project the script is told belongs to a given device (`--device <id> <project>...`): parse the header ID and metadata block with the existing `pattern_file.py` functions, write `<stem>.sidecar.toml` with a single `deployment_history` entry, strip the metadata block, and reduce the header to name-only. Known candidates: `H26-Finale` and `test-pattern`, whose IDs were minted on the `10.0.1.107` device, so this step waits on that device's ID.
4. For every other pattern file (older projects, unknown device): strip the metadata block and the header ID, and write **no sidecar**. They get fresh IDs on their next deploy. Reconstructing history for these is not worth a special case, and a sidecar entry with an unknown device ID is exactly the kind of complexity every future consumer would have to handle. The April `.pbb` backup was checked and does not settle membership either way, since it predates almost all of the recorded IDs.
5. Create a `project.toml` per project in the all-defaults commented-out form from 3.2, uncommenting `pixel_map = "pixel-map.js"` for `daft26-turtle-curtain`.
6. Update the docs, specifically:
   - Root `CLAUDE.md`: the *Pattern File Header* section (name-only header), the *Auto-Generated Metadata Block* section (replace with a description of the sidecar), the *Pattern File Naming Convention* section (prefix, optional ordinals, `projects/` paths, `.sidecar.toml` in the file tree), and the *Using PixelBlaze MCP Tools* section (the `device` / `project` parameters, and how a device is named).
   - `README.md`: the *Setup* steps (no `.env`; `devices.toml` instead), the tool table (new tools), and *Workspace Structure*.
   - Per-project `CLAUDE.md` files: move device facts out of the frankensparker one into the registry `notes`; fix any `project-*` path references.
   - `.gitignore`: drop the `.env` lines once nothing reads it.

Legacy `NN-name.js` filenames in `layered-acrylic` and `sound-level-meter` are a separate cleanup and not bundled with this.

## 8. Open questions

### 8.1 TOML and comment preservation (decided)

**TOML for all three files, via `tomlkit`.** The question was whether Python's built-in TOML support lets tooling update a file while keeping its comments. **No.** The standard library `tomllib` (3.11+) is read-only; there is no `tomllib.dump`. The two write options are:

- `tomli-w`: writes TOML from a plain dict. Comments, key order, and formatting are lost on every rewrite, because the dict never had them.
- `tomlkit`: parses into a document model that keeps comments, whitespace, key order, and quoting style, and writes them back unchanged except for the values you touched. It also understands native datetimes and arrays of tables (`[[deployment_history]]`), which the sidecar leans on. Pure Python, one dependency, used by Poetry for exactly this job.

So the plan uses `tomlkit` for reading and writing everywhere. The rule is: **tooling only touches keys it owns** (`name` and `host` in the registry; everything in the sidecar; nothing in `project.toml` today), and always goes through `tomlkit` so everything else, comments included, survives.

Practical note on the sidecar: because tooling rewrites `deployment_history` entries on every deploy, comments *inside* a history entry will not reliably survive reordering. Top-of-file comments and comments on keys outside the history do. That is a fine trade for a file that is mostly tool-written. The tooling writes the explanatory comments shown in 3.3 itself when it creates a sidecar, so they are present without anyone having to add them.

### 8.2 Offline mode scope

Keep the global flag file, make it a per-device `offline = true` in the registry (now allowed, since tooling can write TOML safely), or drop the flag file for an in-memory toggle plus the `PIXELBLAZE_OFFLINE` env var. Low priority; leaving as-is is fine for phase 1.

### 8.3 Remaining live-device check

The `10.0.1.107` device (`PB LQ 56C SENSOR`) was still unreachable. Its chip ID is needed for the registry stub in 3.1 and for migration step 3. Everything else that needed a live device (ID source, ID stability against the beacon, name length) was settled against `10.0.1.106`; see 3.1 and 3.4.

## 9. Phasing

Each phase is independently shippable and leaves the workspace working.

1. **Layout and config refactor (no sidecar yet).** `projects/` move, `devices.toml`, `project.toml`, `tomlkit`, call-time resolution, `device` / `project` parameters on every tool, chip ID verification on connect, `list_devices` / `discover_devices`, and the `pattern_name_prefix` / optional-ordinal naming convention. The header ID and in-file metadata block stay as they are for this phase; without a sidecar, resolution chain steps 2 and 3 do not exist yet, so `device` is simply required for a while. This phase alone removes the restart problem and the `.env` dependency.
2. **Sidecar and migration.** `<stem>.sidecar.toml`, name-only headers, migration script, docs updates. Own commit. Enables the no-argument redeploy.
3. **Pixel map deployment.** Section 5.
4. **Controls.** Section 6, after the `set_control` merge fix.
5. **Conveniences.** `deploy_project`, session defaults if wanted.

## 10. Verification and acceptance

Add `pytest` as a dev dependency and a `tests/` directory in phase 1. Keep the tests small and file-based; nothing here needs a device.

Unit tests, by phase:

1. **Phase 1.** `canonical_pattern_name()` for every combination of prefix (default, override, empty) and `ordinals` (`auto`, `none`, explicit ordinal present). Device-name-to-stem round trip. `resolve_device()` for each step of the chain, including the ambiguous-name error and the ad-hoc host path. Registry and manifest validation errors on a misspelled key. `list_devices` / `discover_devices` rewriting `devices.toml` with a comment on every line and asserting the comments survive byte-for-byte outside the touched keys.
2. **Phase 2.** Sidecar round trip through `tomlkit`: create, add a second device entry, redeploy to the first (moves to front, updates in place), delete an entry; assert the top-of-file comment survives and value types (float, bool, three-float array) round-trip unchanged. Migration script on a fixture copy of a stamped pattern file: sidecar content, stripped block, name-only header, and idempotence on a second run.
3. **Phase 3.** Map resolution order (per-pattern, project, none) and the hash comparison deciding whether to push.
4. **Phase 4.** First-deploy seeding vs. redeploy read-back, driven by a fake `Pixelblaze` object recording the calls it received.

Smoke test against `10.0.1.106`, within the constraints in section 0, at the end of each phase:

- `list_devices(check=True)` reports the live ID matching the registry key and does not rewrite the file when nothing changed.
- `create_pattern(project="test-pattern", device="PB LQ 0A4 SENSOR", ...)` with a trivial pattern lands on the device under the prefixed name, and `update_pattern` on its ID finds the local file without a `device` argument (phase 2 onward).
- `delete_pattern` on that ID removes it from the device and leaves the sidecar as it was.
- Point `devices.toml` at a wrong host for the entry, or a wrong ID, and confirm the refusal message names both values.

Definition of done for the whole plan: `.env` is gone, no tool reads `PROJECT_FOLDER`, every project lives under `projects/`, every deployed pattern in `H26-Finale` and `test-pattern` has a sidecar whose front entry matches the device, and `TODO.md` has lost the items listed at the top of this plan.

