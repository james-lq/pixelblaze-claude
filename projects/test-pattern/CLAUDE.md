# test-pattern

Scratch project for verifying that the `pixelblaze-claude` tooling (MCP server, pattern file conventions, deploy/update round-trip) works against the current Pixelblaze device. Patterns here are throwaway functionality tests, not production effects.

## Device

- Name: `Pixelblaze_047B0E`
- IP: `10.0.1.122` (set via `PIXELBLAZE_HOST` in the root `.env`)
- Board: `pb32` (Pixelblaze v3), firmware 3.67, chipId 293646
- No expansion boards detected (`exp: 0`); sound/accel/light/analog sources all 0
- Pixel count: 250
- LED type 2, color order GRB, data speed 3.5 MHz
- Brightness 1.0, max brightness 100
- Sequencer off, no auto-off schedule
- **No pixel map configured** (`getMapFunction()` returned empty). Until a map is set, only `render(index)` is meaningful; `render2D`/`render3D` fall back to 1D.

Device snapshot captured 2026-09-05; see `README.md` for the raw config dump.

## Goals

1. Confirm each MCP tool works end to end: list patterns, get device info, get active pattern, create pattern, update pattern, set controls, set brightness, delete pattern.
2. Exercise the local pattern file conventions (`NN Name.js`, header comment block, auto-generated metadata block).
3. Keep test patterns simple and obviously visible on a bare 250-pixel strip: solid colors, single-pixel chasers, index ramps, slider-driven hue.

## Conventions

Follow the root `CLAUDE.md`. Test patterns should be prefixed `TEST ` in their Pixelblaze display name so they are easy to find and bulk-delete on the device later.
