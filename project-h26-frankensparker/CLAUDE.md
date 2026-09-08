# project-h26-frankensparker

Halloween 2026 project: "Frankensparker" — electrical spark / arc effects on LED strip.

## Hardware

Prototyping rig (as of 2026-09-07): Pixelblaze **`PB LQ 56C SENSOR`** at **10.0.1.107** (firmware 3.67), set in the root `.env` as `PIXELBLAZE_HOST`.

**500 pixels** driven through an **Output Expander**, wired as two identical 250-pixel strips:

| Expander channel | Pixel indices | Count |
|---|---|---|
| 0 | 0–249 | 250 |
| 1 | 250–499 | 250 |

The two strips share one continuous index space, so `render(index)` sees 0–499 with the seam at index 250. Whether the strips run parallel, end-to-end, or mirrored is not yet decided — until it is, keep expressing positions as fractions of the strip so patterns survive a change in layout or pixel count.

**No pixel map for this project** — write `render(index)` only, never `render2D`. (The device currently still holds the `project-sound-level-meter` mapper, an 8x12 / 100-pixel grid that does not describe this rig; clear it before relying on any mapped behaviour.)

**Power ceiling — the rig browns out at full brightness.** Measured 2026-09-07 with `02 Frankensparker aftershock` at `sliderSparkWidthFractionOfStrip = 0.505`: at global brightness `1.0` the device hard-resets every few seconds (uptime never gets past ~6 s, status LED flashes, both strips drop out together) while `vmerr` stays 0 and free memory stays flat — so it is a supply brownout, not a firmware or pattern fault. At `0.90` and below, uptime accumulates indefinitely. Sparks are white (`hsv(0, 0, v)`), so every lit pixel draws all three channels at roughly 60 mA; a triangular spark covering half the strip is on the order of 7-8 A on top of the quiescent draw.

Consequences for pattern design here: treat total lit pixels x brightness as a real budget, not a free parameter. Wide sparks, many simultaneous aftershocks, and channels firing in lockstep all stack onto the same instant of peak draw — staggering channels spreads the load in time as well as looking better. Before blaming a pattern for a crash, check `uptime` and `rebootCounter` in the device statistics and re-test at low brightness: if the fault disappears, it is power. Note that a bad enough brownout does not present as periodic resets at all — in the 2026-09-07 measurement the device stopped answering entirely (`Host is down` / connection timeouts) for 21 seconds straight and only came back once brightness was lowered. **A Pixelblaze that has vanished from the network is a power suspect, not just a WiFi suspect.**

**Known config discrepancy:** the two channels are set to different color orders (channel 0 `RGB`, channel 1 `GRB`). If the strips really are identical, one of them will render red and green swapped and the expander config needs fixing.

## Design principles

- Sparks are bright, white, and short-lived: high contrast against long dark gaps rather than continuous animation.
- Timings are specified in real units (milliseconds, seconds) and driven by accumulated `delta`, not `time()`, so they stay exact and fps-independent.
- Spark widths are expressed as a fraction of the strip, not a pixel count.

## Conventions

Follow the root `CLAUDE.md` for file naming, headers, and the metadata block.
