# TODO — H26-Finale

Open items for this project only. Workspace and MCP tooling items live in the root `TODO.md`.

## Channel engine

The per-channel engine landed in `02 Frankensparker aftershock` (geometry from `chPixelCount`, index arithmetic for channel identity, `sliderChannelSync` for phase). These are the remaining planned steps.

- Per-channel parameter table: give each channel its own cycle time, travel time, spark width and echo count from a table in the source, plus a variance factor so channels differ without needing a control per channel. Values in source rather than in controls so they are version-controlled and survive a reboot.

- Per-channel effect selection, so each channel can run a different effect rather than the same one with different parameters. The language has no `switch`, so use an array of lambdas as a lookup table. Closures are not supported, so the lambdas must take `(channel, pos)` as arguments and read globals — design for that from the start rather than discovering it.

- Collapse `01 Frankensparker basic` into `02` as an echo-count-of-zero configuration. The two patterns are the same clock, the same triangular spark and the same colour; `01` is `02` with `aftershocks = 0`. Right now `01` is unconverted and still treats the whole rig as one strip, so the two behave inconsistently.

- Test the declared-vs-device pixel count mismatch path. `chPixelCount` and the device's `pixelCount` setting are independent and can disagree, and rendering is clamped to the smaller of the two so a mismatch should show as dark pixels rather than garbage. That clamp has never actually fired — `pixelDelta` has been 0 for every test so far.

- Scale test at 4 channels without buying hardware, by bumping the device `pixelCount` and the `chPixelCount` table together. The arithmetic and the frame rate cost are both fully exercised even though channels 3 and 4 have no strip attached. Doing this also exercises the mismatch clamp above if the two are deliberately set inconsistently.

- Keep long-term reuse in mind when refactoring the channel handling code, so it is easy to lift out later — but do not let that shape or delay the pattern work now. The general mechanism is tracked in the root `TODO.md` under **Code sharing between patterns**.

## Polish

- Moving `sliderChannelSync` re-seeds the phase offsets, which causes a visible jump on every channel except channel 0. Acceptable while tuning; ease the transition if it becomes annoying.

- Watch for spark steppiness as channel count grows. `render()` runs per pixel, so frame rate falls as pixels are added; at roughly 30 fps a 250 ms traverse gives only 7-8 discrete head positions and the spark reads as stepped rather than smooth. The fix if it appears is a longer `travelSeconds` or a wider `litFraction` so consecutive frames overlap.
