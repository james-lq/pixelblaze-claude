# H26-Barbie

Halloween 2026 project: "Barbie".

## Hardware

Controller: **`0x00AC00A4`** ("PBLQ 0A4 H26-Barbie") in the workspace `devices.toml`,
which carries the device-level facts — board, firmware, colour order. Referenced by
chip ID rather than address so this stays correct when DHCP moves it, and by chip ID
rather than name so it survives the next rename.

**50 pixels, one strip, no output expander.** This is the sensor-board Pixelblaze that
used to be the bench spare; it is the Barbie rig's controller for now, and may be
swapped for a dedicated board later.

**No pixel map, deliberately.** A stale map from an earlier project was cleared by hand
on 2026-09-09 and this project declares none. So:

- Write `render(index)` only, never `render2D`. Exporting both makes Pixelblaze use the
  1D renderer anyway, so a `render2D` here would be dead code that looks live.
- Express positions as fractions of `pixelCount`, not as pixel indices, so patterns
  survive both a change of strip length and a move to the final rig.

**Power.** 50 px is a small load and brightness 1.0 has been fine. That headroom is a
property of *this* controller, not of the patterns — re-check it if the strip grows.

## Design principles

- Warm, bright, high-key palette — yellows through whites.
- See **Device Crashes and Power Brownouts** in the workspace `CLAUDE.md` before
  raising overall brightness. White is the worst case for current draw, so
  effects that light many pixels white at one instant are the ones to watch.
