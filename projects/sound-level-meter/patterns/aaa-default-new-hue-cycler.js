// AAA Default New Hue Cycler
//
// Simple hue cycler: all LEDs cycle through the full color wheel
// over time, with hue offset by position so the strip shows a
// rainbow that rotates.
//
// Design: Minimal pattern — t1 drives the global hue offset at a
// steady pace (time(0.1)), and each pixel's index/pixelCount adds
// a positional spread across the full hue wheel.

export function beforeRender(delta) {
  t1 = time(.1)
}

export function render(index) {
  h = t1 + index/pixelCount
  s = 1
  v = 1
  hsv(h, s, v)
}
