// 01 RGB 1D Chaser Cycle
/*
  Effect: a single bright dot with a short fading tail travels from pixel 0
  to the end of the strip and back again. Each time it completes a full
  out-and-back trip the colour steps to the next in a fixed cycle:
  red, green, blue, red, ...

  Design notes:
  - Functionality test for the pixelblaze-claude tooling, not a real effect.
  - 1D only (render(index)); the device has no pixel map.
  - Motion is an accumulated phase (0..1 per round trip) advanced by delta
    in beforeRender, so timing is fps-independent and the wrap point is
    detectable: that is where the hue index increments.
  - Round-trip period is a number input (seconds) rather than a slider, so
    it can be set exactly. Clamped to >= 0.05 s to avoid divide-by-zero.
  - Control labels are derived by Pixelblaze from the function names
    (CamelCase split into words), so they cannot contain punctuation.
  - Head position is triangle(phase): 0 -> 1 during the first half of the
    phase (outbound), 1 -> 0 during the second half (return).
  - The tail always trails the direction of travel, so it flips at each end.
  - Hue is looked up from a 3-entry array rather than computed, so the
    sequence is exactly red (0), green (1/3), blue (2/3).
*/

var period = 4         // seconds per round trip, i.e. seconds per colour
var width = 0.5        // tail length as a fraction of pixelCount

// Seconds each colour is shown, which is one full out-and-back trip
export function inputNumberSecondsPerColor(v) { period = max(v, 0.05) }
// Tail length as a share of the strip: slider value is the fraction of pixelCount
export function sliderWidthPercentOfPixelCount(v) { width = max(v, 0.01) }

var hues = [0, 1/3, 2/3]   // red, green, blue
var hueIndex = 0
var phase = 0              // 0..1, one full out-and-back
var head = 0               // 0..1 position along the strip
var outbound = 1           // 1 while travelling 0 -> end, 0 on the way back
var hue = 0

export function beforeRender(delta) {
  phase += delta / 1000 / period
  if (phase >= 1) {
    phase -= 1
    hueIndex = (hueIndex + 1) % 3
  }
  head = triangle(phase)
  outbound = phase < 0.5
  hue = hues[hueIndex]
}

export function render(index) {
  pos = index / pixelCount
  // Distance behind the head, measured against the direction of travel
  d = outbound ? head - pos : pos - head
  v = clamp(1 - d / width, 0, 1)
  v = v * v * v
  hsv(hue, 1, v)
}
