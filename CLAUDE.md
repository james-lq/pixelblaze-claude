# PixelBlaze AI Assistant Context

This workspace uses a PixelBlaze MCP server to develop LED patterns. Hardware-specific context (pixel layout, coordinate system, device IP, design principles) lives in each project's own `CLAUDE.md` inside its `project-*/` folder — loaded automatically when working in that directory.

## Using PixelBlaze MCP Tools

All `mcp_pixelblaze_*` tools are **deferred** and must be loaded via `tool_search` before they can be called. Skipping this step causes a cryptic `Cannot read properties of undefined (reading 'invoke')` error that looks like a network failure but isn't.

**Always do this first, before any PixelBlaze tool call:**
```
tool_search("pixelblaze list patterns")   // or whatever action is needed
```
Then call the tool returned by the search. This applies to every tool in the `mcp_pixelblaze_*` and `mcp_pixelblaze_docs_*` namespaces.

## macOS: Local Network Access

On macOS Ventura and later, each app must be explicitly granted permission to access local network devices. If the PixelBlaze is unreachable from VS Code or the terminal (connection refused, no route to host, or similar) but is accessible from a browser, this permission is the most likely cause.

**Fix:** Open **System Settings → Privacy & Security → Local Network** and enable access for **Visual Studio Code**. Then restart VS Code so the MCP server process inherits the updated permission.

## Pattern Development Workflow

1. **Always call `docs_get_api_reference`** before writing new pattern code
2. Use `render2D(index, x, y)` for 2D layouts; `render(index)` for 1D strips
3. Use `beforeRender(delta)` for animation state updates
4. Export UI controls with `export var slider*` / `export var hue*` naming conventions
5. Test with `pixelblaze_create_pattern` — it auto-activates the new pattern
6. Iterate with `pixelblaze_update_pattern`

### Pattern File Naming Convention

Pattern files live in the project's `patterns/` folder and use a 2-digit ordinal prefix, spaces, and natural capitalization — matching the Pixelblaze display name exactly (minus the `.js` extension):

```
patterns/
  NN Name With Spaces.js          ← pattern code
  NN Name With Spaces.mapper.js   ← pixel map for that pattern (if 2D/3D)
```

Examples:
- `patterns/01 Spectrum Analyzer.js`
- `patterns/02 Spectrum Analyzer 2D.js`
- `patterns/02 Spectrum Analyzer 2D.mapper.js`

The Pixelblaze display name for a pattern should be identical to its filename without the `.js` extension. This does mean that pattern names are currently limited to legal JS file names on Windows, Mac, and Linux. Filenames must be unique within a project.

### Pattern File Header
Every pattern JS file should start with a comment block containing:
1. **Pattern name and device pattern ID** — for updating via `pixelblaze_update_pattern`
2. **Effect description** — what the pattern looks like, in plain language
3. **Design notes** — key implementation decisions, algorithms used, and gotchas


### Auto-Generated Metadata Block

> TODO: Update this metadata mechanism to write to a sidecar file instead.
> I've realized that stashing a hash (etc) in the source file itself is an anti-pattern.

The MCP tooling appends a metadata block to the **end** of every pattern file after it is deployed or created. **Never edit this block manually** — it is fully managed by the tooling.

```js
// ---- pixelblaze-mcp metadata----
// @deployed: 2026-01-15T10:30:00Z
// @deployed-hash: a1b2c3d4
// @modified-since-deployed: false
```

- `@deployed` — ISO 8601 timestamp of the last deploy to the device; `(pending)` if the file was created locally but never deployed
- `@deployed-hash` — SHA-256 (first 8 hex chars) of the code at the time of the last deploy, used to detect local edits made after deployment
- `@modified-since-deployed` — `true` if the local file has been edited since the last deploy; `false` if in sync with the device

When `modified-since-deployed` is `true`, use `pixelblaze_update_pattern` to push the changes to the device.

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

