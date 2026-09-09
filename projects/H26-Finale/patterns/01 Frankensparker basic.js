// 01 Frankensparker basic — Pattern ID: dBdPAvWPDRSnqi3c8
/*
  Effect: a single bright white spark runs the length of the strip in
  250 ms, then the strip goes dark until the next spark 5 seconds later.
  The spark is a triangular brightness peak covering about 10% of the
  strip, so it reads as a short streak of light rather than a single dot.

  Design notes:
  - 1D only (render(index)); the device has no pixel map.
  - Time is accumulated from delta rather than taken from time(), so the
    250 ms sweep and 5 s repeat are exact real-world durations and are
    independent of frame rate.
  - The cycle clock `t` counts seconds from the start of a spark. While
    t <= travel seconds the spark is on screen; the rest of the cycle is
    dark. Wrapping uses subtraction of the period, not mod(), so a long
    frame cannot skip a whole cycle.
  - Head position is t / travel, i.e. a linear ramp 0 -> 1 across the
    strip; this is the rising-then-falling triangle's apex, not a wave().
  - Brightness falls off linearly either side of the head over halfWidth,
    so the total lit span is litFraction of the strip. At the two ends
    part of the triangle hangs off the strip, so the spark appears to
    grow in and shrink out at the extremes.
  - Colour is hsv(0, 0, v): zero saturation is pure white at full value.
  - Positions are fractions of the strip (index / (pixelCount - 1)) so
    the timing and width hold on a strip of any length.
*/

var cycleSeconds = 5      // seconds between the start of one spark and the next
var travelSeconds = 0.25  // seconds for the spark to cross the whole strip
var litFraction = 0.1     // share of the strip lit by the spark at any instant

// Seconds between sparks
export function inputNumberSecondsBetweenSparks(v) { cycleSeconds = max(v, 0.05) }
// Seconds the spark takes to travel the whole strip
export function inputNumberSparkTravelSeconds(v) { travelSeconds = max(v, 0.01) }
// Share of the strip lit by the spark, as a fraction between 0 and 1
export function sliderSparkWidthFractionOfStrip(v) { litFraction = max(v, 0.005) }

var t = 0          // seconds since the current spark started
var head = 0       // 0..1 position of the spark's peak along the strip
var halfWidth = 0.05
var sparking = 0   // 1 while the spark is on the strip

export function beforeRender(delta) {
  t += delta / 1000
  while (t >= cycleSeconds) t -= cycleSeconds
  sparking = t <= travelSeconds
  head = t / travelSeconds
  halfWidth = litFraction / 2
}

export function render(index) {
  v = 0
  if (sparking) {
    pos = index / (pixelCount - 1)
    v = clamp(1 - abs(pos - head) / halfWidth, 0, 1)
  }
  hsv(0, 0, v)
}

// ---- pixelblaze-mcp metadata----
// @deployed: 2026-09-06T03:05:51Z
// @deployed-hash: a2b066c7
// @modified-since-deployed: false
