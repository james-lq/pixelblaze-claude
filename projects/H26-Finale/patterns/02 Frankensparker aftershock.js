// 02 Frankensparker aftershock — Pattern ID: mSXJ5etzaarWuZSPv
/*
  Effect: every output expander channel runs its own copy of the spark. On
  each channel a bright white spark crosses that channel's strip in 250 ms
  and is chased by two dimmer aftershocks that flash back from the far end
  at twice the speed; the channel is then dark until the next spark 5
  seconds later. In this phase every channel is configured identically and
  starts in phase, so all channels fire together.

  Design notes:
  - 1D only (render(index)); the device has no pixel map. Channel identity
    comes from index arithmetic rather than from a map, so adding or
    removing a strip needs no map edit and cannot rescale the coordinates
    of the other channels.
  - chPixelCount declares the physical pixel count of each expander
    channel, in channel order, and is the single source of truth for
    geometry here. A zero entry ends the list. It assumes the expander
    gives channels contiguous ascending start indexes (0, 250, ...),
    which is how the device is configured.
  - Because channel lengths are allowed to differ, index -> channel cannot
    be a divide. render() does a bounded scan over at most
    MAX_CHANNELS - 1 start offsets with an early exit, which at these
    channel counts costs about what the divide it replaces would.
  - Position is normalised within the channel (0..1 across that channel's
    own strip), so timings hold on a channel of any length: a spark always
    takes travelSeconds to cross its own strip, not some share of the rig.
  - chPixelCount and the device's own pixelCount setting are independent
    and can disagree. The exported pixelDelta shows the difference in the
    Var Watcher, where 0 means they agree. Rendering is clamped to the
    smaller of the two, so a mismatch shows up as dark pixels rather than
    as garbage. These diagnostics are exported variables and deliberately
    not showNumber controls: an output control makes the UI refresh the
    whole control set very frequently, and that refresh overwrites an
    input control while it is being typed into.
  - sliderChannelSync staggers the channels in time: at 1 they fire together,
    at 0 they are spread evenly across one cycle. Offsets are applied
    relative to channel 0 rather than by resetting the clocks, so moving the
    control never restarts channel 0. Staggering also spreads the peak
    current draw over time, which matters on this rig (see CLAUDE.md).
  - All per-channel work happens in beforeRender (channelCount iterations
    per frame). render() only looks values up and evaluates the spark
    shape, so the per-pixel cost stays flat as channels are added.
  - Colour is hsv(0, 0, v): zero saturation is pure white at full value.
*/

var MAX_CHANNELS = 8

// Physical pixel count of each expander channel, in channel order.
// A zero entry ends the list; channels at or after it are not rendered.
var chPixelCount = [250, 250, 0, 0, 0, 0, 0, 0]

// ---- derived channel geometry ----
var chPixelStart = array(MAX_CHANNELS)  // first pixel index of each channel
var chSpan = array(MAX_CHANNELS)        // divisor for 0..1 position, never 0
// Exported for the Var Watcher rather than surfaced as showNumber controls:
// output controls make the UI refresh the whole control set very frequently,
// which overwrites an input control while it is being typed into.
export var channelCount = 0    // leading non-zero chPixelCount entries
export var declaredPixels = 0  // total pixels claimed by the channels
export var pixelDelta = 0      // declaredPixels - pixelCount; 0 means they agree
var activePixels = 0           // pixels actually rendered

function initChannels() {
  var i
  channelCount = 0
  declaredPixels = 0
  for (i = 0; i < MAX_CHANNELS; i++) {
    if (chPixelCount[i] <= 0) break
    chPixelStart[i] = declaredPixels
    chSpan[i] = max(chPixelCount[i] - 1, 1)
    declaredPixels += chPixelCount[i]
    channelCount = i + 1
  }
  // A declared total larger than the device's pixelCount would run the last
  // channel off the end of the strip; clamp so the excess just stays dark.
  activePixels = min(declaredPixels, pixelCount)
  pixelDelta = declaredPixels - pixelCount
}
initChannels()

// ---- base parameters, applied to every channel in this phase ----
var cycleSeconds = 5      // seconds between the start of one spark and the next
var travelSeconds = 0.25  // seconds for the spark to cross a channel's strip
var litFraction = 0.1     // share of the strip lit by the spark at any instant
var aftershocks = 2       // how many echo sparks follow the leading one
var echoFade = 0.5        // brightness multiplier applied per echo
var channelSync = 1       // 1 = channels fire together, 0 = evenly staggered

// ---- per-channel configuration, filled from the base parameters ----
var chCycle = array(MAX_CHANNELS)
var chTravel = array(MAX_CHANNELS)
var chHalfWidth = array(MAX_CHANNELS)
var chEchoes = array(MAX_CHANNELS)
var chFade = array(MAX_CHANNELS)

// ---- per-channel state ----
var chT = array(MAX_CHANNELS)      // seconds since this channel's spark started
var chHead = array(MAX_CHANNELS)   // 0..1 position of the spark's peak
var chLevel = array(MAX_CHANNELS)  // brightness of the spark currently running

// array() does not promise zeroed contents, and an unset clock leaves the
// channels running at arbitrary offsets from each other, so start them
// explicitly. This is also where per-channel phase offsets will be seeded
// once the sync control exists.
function resetChannelClocks() {
  var i
  for (i = 0; i < MAX_CHANNELS; i++) {
    chT[i] = 0
    chHead[i] = 0
    chLevel[i] = 0
  }
}
resetChannelClocks()

// Spread the channels across the cycle according to channelSync. Offsets are
// applied relative to channel 0's clock rather than by resetting the clocks,
// so re-phasing never restarts channel 0 and stays correct once channels have
// different cycle lengths.
function applyChannelPhase() {
  var i, offset
  for (i = 0; i < channelCount; i++) {
    // At sync 1 every channel sits on channel 0's clock; at sync 0 they are
    // spread evenly across one full cycle.
    offset = (1 - channelSync) * (i / channelCount) * chCycle[i]
    chT[i] = chT[0] + offset
    while (chT[i] >= chCycle[i]) chT[i] -= chCycle[i]
  }
}

// Push the base parameters out to every channel. Later phases vary the
// values per channel here; for now each channel gets the same ones.
function applyChannelConfig() {
  var i
  for (i = 0; i < MAX_CHANNELS; i++) {
    // Guard the cycle length: beforeRender wraps chT by repeated subtraction,
    // so a zero here would spin forever.
    chCycle[i] = max(cycleSeconds, 0.05)
    chTravel[i] = max(travelSeconds, 0.01)
    chHalfWidth[i] = max(litFraction, 0.005) / 2
    chEchoes[i] = aftershocks
    chFade[i] = echoFade
  }
  // Offsets are expressed in cycle-lengths, so re-derive them here.
  applyChannelPhase()
}
applyChannelConfig()

// Seconds between sparks
export function inputNumberSecondsBetweenSparks(v) {
  cycleSeconds = max(v, 0.05)
  applyChannelConfig()
}
// Seconds the leading spark takes to travel the whole strip
export function inputNumberSparkTravelSeconds(v) {
  travelSeconds = max(v, 0.01)
  applyChannelConfig()
}
// How many aftershocks flash back after each leading spark
export function inputNumberAftershockCount(v) {
  aftershocks = max(floor(v), 0)
  applyChannelConfig()
}
// Share of the strip lit by the spark, as a fraction between 0 and 1
export function sliderSparkWidthFractionOfStrip(v) {
  litFraction = max(v, 0.005)
  applyChannelConfig()
}
// How much each aftershock dims relative to the one before it
export function sliderAftershockFade(v) {
  echoFade = clamp(v, 0.05, 1)
  applyChannelConfig()
}
// How closely the channels fire together: 1 is lockstep, 0 spreads them evenly across the cycle
export function sliderChannelSync(v) {
  channelSync = clamp(v, 0, 1)
  applyChannelPhase()
}

export function beforeRender(delta) {
  var dt = delta / 1000
  var c, t, travel, echoTravel, elapsed, n
  for (c = 0; c < channelCount; c++) {
    chT[c] += dt
    // Subtract the period rather than using mod(), so a long frame cannot
    // skip a whole cycle.
    while (chT[c] >= chCycle[c]) chT[c] -= chCycle[c]

    t = chT[c]
    travel = chTravel[c]
    if (t < travel) {
      // Leading spark: start -> end of this channel, at full brightness.
      chHead[c] = t / travel
      chLevel[c] = 1
    } else {
      // Aftershocks: each runs end -> start at half the travel time, so the
      // index found here also gives the echo's depth and therefore its fade.
      echoTravel = travel / 2
      elapsed = t - travel
      n = floor(elapsed / echoTravel)
      if (n < chEchoes[c]) {
        chHead[c] = 1 - (elapsed - n * echoTravel) / echoTravel
        chLevel[c] = pow(chFade[c], n + 1)
      } else {
        chLevel[c] = 0
      }
    }
  }
}

export function render(index) {
  v = 0
  if (index < activePixels) {
    // Bounded scan with early exit: channel lengths may differ, so the
    // channel a pixel belongs to cannot be found by dividing.
    c = 0
    while (c < channelCount - 1 && index >= chPixelStart[c + 1]) c++

    if (chLevel[c] > 0) {
      // Position within this channel's own strip, so the spark's speed and
      // width are relative to the channel rather than to the whole rig.
      pos = (index - chPixelStart[c]) / chSpan[c]
      v = chLevel[c] * clamp(1 - abs(pos - chHead[c]) / chHalfWidth[c], 0, 1)
    }
  }
  hsv(0, 0, v)
}

// ---- pixelblaze-mcp metadata----
// @deployed: 2026-09-08T02:59:12Z
// @deployed-hash: 4eebd6b9
// @modified-since-deployed: false
