# H26-Finale

Halloween 2026 spark/arc patterns for a single Pixelblaze LED strip. See `CLAUDE.md` for working context.

## Patterns

| Pattern | Effect |
|---|---|
| `01 Frankensparker basic` | A single bright white spark sweeps the length of the strip in 250 ms, then the strip is dark until the next spark 5 s later. |
| `02 Frankensparker aftershock` | Per-channel version: every output expander channel runs its own copy of the spark across its own strip, each chased by dimmer echo sparks that flash back from the far end at twice the speed. Channel geometry is declared in the `chPixelCount` table at the top of the file. |

## Notes

Prototyping on `PB LQ 56C SENSOR` (10.0.1.107): 500 pixels as two 250-pixel strips behind an Output Expander. Final placement and physical arrangement of the two strips are not decided. See `CLAUDE.md` for the full wiring map.

## Channel engine

`02` runs the per-channel engine: `chPixelCount` at the top of the file declares each expander channel's pixel count, a zero entry ends the list, and channel identity comes from index arithmetic rather than a pixel map. Every channel currently takes the same parameters, so they run in lockstep; per-channel variation and a sync control come next. The exported `channelCount`, `declaredPixels` and `pixelDelta` variables show up in the editor's Var Watcher: `pixelDelta` is 0 when the declared channel total agrees with the device's own pixel count. These are deliberately exported variables rather than `showNumber` controls — an output control makes the web UI refresh the whole control set very frequently, which overwrites an input control while you are typing into it.

`01` has not been converted and still treats the whole rig as one strip.
