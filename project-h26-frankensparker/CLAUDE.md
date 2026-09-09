# project-h26-frankensparker

Halloween 2026 project: "Frankensparker" — electrical spark / arc effects on LED strip.

## Hardware

Prototyping rig (as of 2026-09-07): Pixelblaze **`PB LQ 56C SENSOR`** at **10.0.1.107** (firmware 3.67), set in the root `.env` as `PIXELBLAZE_HOST`.

**500 pixels** driven through an **Output Expander**, wired as two identical 250-pixel strips:

| Expander channel | Pixel indices | Count |
|---|---|---|
| 0 | 0–249 | 250 |
| 1 | 250–499 | 250 |

**One strip per expander channel**, one-to-one: each channel drives exactly one physical strip, and that is the working plan as more strips are added. Strips are not reversed or mirrored relative to each other, so patterns need no per-channel direction handling. The strips still share one continuous index space, so `render(index)` sees 0–499 with the seam at index 250. Keep expressing positions as fractions of a channel's own strip so patterns survive a change in strip length or channel count.

**No pixel map for this project** — write `render(index)` only, never `render2D`. (The device had been carrying the `project-sound-level-meter` mapper, an 8x12 / 100-pixel grid that does not describe this rig; it was cleared by hand through the web UI on 2026-09-07.)

**Power ceiling.** Brightness 1.0 is fine with the current configuration. It was not always: measured 2026-09-07, a wide spark (`sliderSparkWidthFractionOfStrip = 0.505`) at global brightness 1.0 browned the device out — resetting every few seconds, then dropping off the network entirely for 21 seconds — while `vmerr` stayed 0 and free memory stayed flat. Narrowing the spark restored headroom. At brightness 0.90 and below the wide spark was stable, so the cliff sat between 0.90 and 1.0.

See **Device Crashes and Power Brownouts** in the workspace `CLAUDE.md` for how to recognise and diagnose this class of fault. The working plan for this project is to rewire channels with independent power injection for the controller vs. the LED strips.

**Expander colour order:** the two channels were originally set to different colour orders (channel 0 `RGB`, channel 1 `GRB`), which would have rendered red and green swapped on one strip. Fixed by hand through the web UI on 2026-09-07.

## Design principles

- Sparks are bright, white, and short-lived: high contrast against long dark gaps rather than continuous animation.
- Timings are specified in real units (milliseconds, seconds) and driven by accumulated `delta`, not `time()`, so they stay exact and fps-independent.
- Spark widths are expressed as a fraction of the strip, not a pixel count.

## Conventions

Follow the root `CLAUDE.md` for file naming, headers, and the metadata block.
