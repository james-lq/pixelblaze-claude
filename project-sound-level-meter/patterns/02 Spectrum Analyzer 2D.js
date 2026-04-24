// 02 Spectrum Analyzer 2D — Pattern ID: (pending)
//
// VU-style spectrum analyzer on an 2D LED grid (see `*.mapper.js` file).
// Visual frequency bin bars fill upward from the bottom.
// Color transitions green (bottom) → cyan (mid) → red (top).
// Peak-hold indicators float above each bar in bright red.
//
// Design notes:
// - Requires the 2D pixel map in `*.mapper.js` configured in the Mapper tab.
// - Set Mapper scaling mode to "Fill" so x and y map independently to 0..1.
// - 8 visual columns = 8 log-scale frequency bins from frequencyData[32].
//   Bin 0 (bass) averages elements 0–9; higher bins get fewer elements (more granular).
//   Boundaries: floor(log(i+1) / log(9) * 32) for i = 0..8.
// - Auto-gain via global PI controller: tracks rolling max
//   bar height and adjusts sensitivity to target 90% fullness.
// - Peak hold: rises instantly to current level, decays at sliderPeakDecay rate.
// - Hue by height: green (h=0.33) at bottom, cyan (h=0.5) at mid, red (h=1.0) at top.

export var frequencyData = array(32)
export var energyAverage = 0

// ---- Layout ----
var NUM_BINS = 8
var NUM_ROWS = 12

// ---- Log-scale frequency bin ranges ----
// Precomputed start/end indices into frequencyData[32].
// Bin 0 (bass): elements 0–9 (10 elements).  Bins 5–7 (treble): 2 elements each.
var freqStart = array(8)
var freqEnd   = array(8)

var _logScale = log(NUM_BINS + 1)   // log(9) ≈ 2.197
var _i, _s, _e
for (_i = 0; _i < NUM_BINS; _i++) {
  _s = floor(log(_i + 1) / _logScale * 32)
  _e = floor(log(_i + 2) / _logScale * 32)
  freqStart[_i] = _s
  freqEnd[_i]   = max(_s + 1, _e)    // guarantee at least 1 element per bin
}

// ---- Per-bin state ----
var binLevels  = array(8)   // smoothed display level per bin (0–1)
var peakLevels = array(8)   // peak-hold level per bin (0–1)
for (_i = 0; _i < NUM_BINS; _i++) {
  binLevels[_i]  = 0
  peakLevels[_i] = 0
}

// ---- PI controller for global auto-gain ----
// Computes sensitivity that keeps the tallest bar near targetMax.
// Ported from "sound - spectrum analyser 1D/2D" by ChrisNZ (KFLiP26).
var targetMax  = 0.9
var averageMax = 0
var pic = array(5)
pic[0] = 0.25    // kp — proportional gain
pic[1] = 1.8     // ki — integral gain
pic[2] = 30      // integrator starting value
pic[3] = 0       // integrator minimum
pic[4] = 100     // integrator maximum

function calcPI(err) {
  pic[2] = clamp(pic[2] + err, pic[3], pic[4])
  return pic[0] * err + pic[1] * pic[2]
}

// ---- UI state ----
var smoothing     = 0.6      // exponential smoothing factor (0 = instant, ~1 = very slow)
var peakDecayRate = 0.1      // level units per second that peak indicators fall
var brightness    = 1.0
var noiseFloor    = 0.0

export function beforeRender(delta) {
  var dt = delta / 1000
  var i, j, sum, raw, level, currentMax, span
  var sensitivity = max(1, calcPI(targetMax - averageMax))

  currentMax = 0
  for (i = 0; i < NUM_BINS; i++) {
    // Average frequencyData over this bin's log-scaled range
    sum  = 0
    span = freqEnd[i] - freqStart[i]
    for (j = freqStart[i]; j < freqEnd[i]; j++) {
      sum = sum + frequencyData[j]
    }
    raw = sum / span
    raw = max(raw - noiseFloor, 0)
    level = clamp(raw * sensitivity, 0, 1)

    // Exponential smoothing for stable bar display
    binLevels[i] = binLevels[i] * smoothing + level * (1 - smoothing)
    currentMax = max(currentMax, level)

    // Peak hold: rise instantly, decay at peakDecayRate per second
    if (binLevels[i] >= peakLevels[i]) {
      peakLevels[i] = binLevels[i]
    } else {
      peakLevels[i] = max(0, peakLevels[i] - peakDecayRate * dt)
    }
  }

  // Rolling average of max bar level feeds back into PI controller
  averageMax = averageMax - averageMax / 50 + currentMax / 50
}

export function render2D(index, x, y) {
  var col       = clamp(floor(x * NUM_BINS), 0, NUM_BINS - 1)
  var level     = binLevels[col]
  var peakLevel = peakLevels[col]

  // Row index from top (0=top, 11=bottom), derived from world-unit y (0=top, 1=bottom)
  var rowFromTop = clamp(floor(y * NUM_ROWS), 0, NUM_ROWS - 1)

  // Bar fills from bottom: bottom litCount rows are lit
  var litCount = floor(level * NUM_ROWS)
  var isLit    = rowFromTop >= (NUM_ROWS - litCount)

  // Peak indicator: single row at the top edge of the peak level
  var peakLitCount = floor(peakLevel * NUM_ROWS)
  var isPeak = (peakLitCount > 0) && (rowFromTop == (NUM_ROWS - peakLitCount))

  // Hue by column height: green (bottom) → cyan (mid) → red (top, wraps in hsv)
  // pos: 0 at bottom (y≈1), 1 at top (y≈0)
  var pos = 1 - y
  var h
  if (pos <= 0.5) {
    h = 0.33 + pos * 0.34    // green (h=0.33) → cyan (h=0.50)
  } else {
    h = 0.5 + (pos - 0.5)    // cyan  (h=0.50) → red  (h=1.0, wraps)
  }

  if (isPeak) {
    hsv(0, 1, brightness)          // bright red peak indicator
  } else if (isLit) {
    hsv(h, 1, brightness * 0.8)   // bar fill: slightly dimmed relative to peak
  } else {
    rgb(0, 0, 0)
  }
}

// 1D fallback when no pixel map is configured
export function render(index) {
  rgb(0, 0, 0)
}

// How responsive bars are to sound changes (low = instant, high = slow/smooth)
export function sliderSmoothing(v) { smoothing = mix(0.0, 0.95, v) }
// How fast peak indicators fall after a loud transient
export function sliderPeakDecay(v) { peakDecayRate = mix(0.02, 0.5, v) }
// Overall LED brightness
export function sliderBrightness(v) { brightness = mix(0.2, 1.0, v) }
// Minimum signal level treated as silence (tune to eliminate ambient noise)
export function sliderNoiseFloor(v) { noiseFloor = mix(0, 0.2, v) }
