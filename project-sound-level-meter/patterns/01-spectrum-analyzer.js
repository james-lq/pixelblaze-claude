// Spectrum Analyzer — Pattern ID: 6bKeDpbiKYDKMKNkE
//
// Effect: 8-band VU-style spectrum analyzer across 2 vertical strings of 50 LEDs.
// Each string holds 4 frequency bins of 12 LEDs, with 1 dark padding pixel at each
// end of each string. Bars fill upward from the bottom of each 12-LED segment.
// Color transitions green (bottom/quiet) → yellow → red (top/loud) per segment.
// Includes peak-hold indicators with configurable decay speed.
//
// Design notes:
// - Uses render(index) with arithmetic pixel mapping — no pixel map needed.
// - String 0 (pixels 0–49)  = bins 0–3 (low frequencies)
// - String 1 (pixels 50–99) = bins 4–7 (high frequencies)
// - Layout per string: [pad] [bin0×12] [bin1×12] [bin2×12] [bin3×12] [pad]
// - frequencyData[32] is averaged into 8 visual bins (4 elements each).
// - Per-bin auto-gain normalization keeps all bands visible regardless of spectrum shape.
// - Peak hold decays continuously; the peak LED uses full brightness as a marker.

export var frequencyData = array(32)
export var energyAverage = 0

// ---- Layout constants ----
var NUM_BINS = 8
var LEDS_PER_BIN = 12
var LEDS_PER_STRING = 50
var BINS_PER_STRING = 4
var FREQ_PER_BIN = 4   // number of frequencyData elements averaged per visual bin

// ---- Per-bin state ----
var binLevels = array(8)   // current smoothed display level (0–1)
var peakLevels = array(8)  // peak-hold level per bin (0–1)
var binMax = array(8)      // running per-bin maximum for auto-gain

// ---- UI control state (with defaults) ----
var gain = 1.0           // manual gain multiplier on top of auto-gain
var peakDecayRate = 0.1  // level units per second that peak falls
var brightness = 1.0
var noiseFloor = 0       // raw freq values below this are treated as silence (tune via slider)

var smoothing = 0.6      // exponential smoothing factor for bar display (0=instant, 1=frozen)
var BIN_MAX_MIN = 0.3    // minimum auto-gain denominator; keeps bars from saturating during silence

// Initialise arrays to safe defaults
var _i
for (_i = 0; _i < NUM_BINS; _i++) {
  binMax[_i] = BIN_MAX_MIN
  peakLevels[_i] = 0
  binLevels[_i] = 0
}

export function beforeRender(delta) {
  var dt = delta / 1000   // convert ms → seconds
  var i, j, sum, raw, level, peakCount

  for (i = 0; i < NUM_BINS; i++) {
    // Average FREQ_PER_BIN consecutive frequencyData elements into each visual bin
    sum = 0
    for (j = 0; j < FREQ_PER_BIN; j++) {
      sum = sum + frequencyData[i * FREQ_PER_BIN + j]
    }
    raw = sum / FREQ_PER_BIN

    // Subtract noise floor so ambient silence produces a zero level
    raw = max(raw - noiseFloor, 0)

    // Per-bin auto-gain: track running max, decaying slowly; never drop below BIN_MAX_MIN
    binMax[i] = max(binMax[i] * 0.997, max(raw, BIN_MAX_MIN))

    // Normalise and apply manual gain multiplier
    level = clamp(raw / binMax[i] * gain, 0, 1)

    // Smooth the bar display to reduce flicker without losing responsiveness
    binLevels[i] = binLevels[i] * smoothing + level * (1 - smoothing)

    // Peak hold: rise instantly, decay at peakDecayRate
    if (binLevels[i] >= peakLevels[i]) {
      peakLevels[i] = binLevels[i]
    } else {
      peakLevels[i] = max(0, peakLevels[i] - peakDecayRate * dt)
    }
  }
}

export function render(index) {
  var s = floor(index / LEDS_PER_STRING)          // which string: 0 or 1
  var localIdx = index % LEDS_PER_STRING          // position within string: 0–49

  // Any pixel beyond the two active strings is dark (device may have more strings configured)
  if (s > 1) {
    rgb(0, 0, 0)
    return
  }

  // Dark padding pixel at each end of each string
  if (localIdx == 0 || localIdx == LEDS_PER_STRING - 1) {
    rgb(0, 0, 0)
    return
  }

  var offset = localIdx - 1                           // 0–47 (4 bins × 12 LEDs)
  var binInString = floor(offset / LEDS_PER_BIN)     // 0–3
  var posInBin = offset % LEDS_PER_BIN               // 0 = top of segment, 11 = bottom
  var binIndex = s * BINS_PER_STRING + binInString   // 0–7

  var level = binLevels[binIndex]
  var litCount = floor(level * LEDS_PER_BIN)         // how many LEDs lit from bottom

  // A pixel is lit if it falls within the bottom `litCount` pixels of the segment
  // (posInBin 11 is bottommost, so lit when posInBin >= LEDS_PER_BIN - litCount)
  var isLit = posInBin >= (LEDS_PER_BIN - litCount)

  // Peak hold: single LED at the topmost lit position for the peak level
  var peakLit = 0
  var peakCount = floor(peakLevels[binIndex] * LEDS_PER_BIN)
  if (peakCount > 0) {
    peakLit = (posInBin == (LEDS_PER_BIN - peakCount))
  }

  // Color by position in segment: bottom (posInBin 11) = green, top (posInBin 0) = red
  // h = 0.33 at posInBin 11, h = 0.0 at posInBin 0
  var h = posInBin / (LEDS_PER_BIN - 1) * 0.33

  if (peakLit) {
    // Peak indicator: full brightness, same hue as position
    hsv(h, 1, brightness)
  } else if (isLit) {
    // Active bar: slightly dimmed relative to peak marker
    hsv(h, 1, brightness * 0.8)
  } else {
    rgb(0, 0, 0)
  }
}

// How much to amplify the signal on top of per-bin auto-gain
export function sliderGain(v) { gain = mix(0.5, 4, v) }
// How fast peak indicators fall after a loud transient
export function sliderPeakDecay(v) { peakDecayRate = mix(0.02, 0.5, v) }
// Overall LED brightness
export function sliderBrightness(v) { brightness = mix(0.2, 1.0, v) }
// Minimum signal level treated as silence (tune to eliminate ambient noise)
export function sliderNoiseFloor(v) { noiseFloor = mix(0, 0.2, v) }

// ---- pixelblaze-mcp metadata----
// @deployed: 2026-04-23T03:53:14Z
// @deployed-hash: f511dce3
// @modified-since-deployed: false
