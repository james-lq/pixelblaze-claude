// 01 Sun Sparkle
/*
  Effect: the strip fills with scattered points of light that swell and fade
  like sun glinting off water. Each spark rises through a saturated golden
  yellow and whitens as it peaks, so the brightest points read as sunlight
  rather than as a yellow LED. Between sparks a faint warm glow keeps the
  strip from going fully black.

  Design notes:
  - Sparks come from Perlin noise rather than random(): each pixel reads its
    own slice of a 3D noise field, and the field is walked along one axis over
    time. A pixel's brightness therefore changes *smoothly*, which is what
    makes a spark swell and fade instead of flickering on for one frame.
  - Neighbouring pixels are spaced a golden-ratio step apart in noise space.
    A step of exactly 1.0 would put every pixel on an integer lattice point,
    where Perlin noise is always 0 and the strip would stay dark; an irrational
    step decorrelates neighbours without ever re-aligning with the lattice.
  - Perlin output clusters near the middle of its range and rarely reaches the
    extremes, so the raw value is stretched about its midpoint before being
    thresholded. Without that, a high density setting would light nothing.
  - Density is deliberately non-linear, and measured rather than assumed. Off
    the device at 50 px, the share of pixels visibly lit (>= 40/255) against
    the Density slider reads:

        slider   0.00   0.25   0.50   0.75   1.00
        lit       0.2%   3.8%  11.5%  23.2%  48.2%

    Fine control sits at the sparse end, which is where the look actually
    changes. The defaults below sit high on that curve, at ~39% lit, which is
    a deliberate choice for this rig: dense and sunlit rather than sparse and
    starry. They were set by eye on the hardware and then measured back.
  - Only the top `density` share of the noise range lights up. smoothstep()
    eases each spark in rather than popping it on, and squaring the result
    steepens the falloff so cores stay tight.
  - Layout-agnostic: 1D render(index) only, positions taken as fractions of
    pixelCount, no pixel map. Do not add render2D here unless the rig gets a
    map, since exporting both makes Pixelblaze ignore the 2D one.
  - Power: sparse by construction, so peak draw is far below a solid fill. The
    cost driver is whitening at the peaks, since white drives all three
    channels. Raising Density and Glow together is what to watch.
*/

// Fraction of the noise range that lights up at any moment. 0.766 measures at
// roughly 39% of pixels visibly lit — a dense, nearly-filled field. Tuned by
// hand on the rig rather than calculated. Only used until a saved slider value
// loads, i.e. on a first deploy to a device with no stored controls yet.
var density = 0.766
// How fast the noise field is walked, i.e. how quickly sparks swell and fade.
var speed = 1.275
// Warm floor so the strip is never fully dark. At 0.15 the floor is clearly
// visible amber rather than a hint, which suits a sun theme: the strip reads as
// glowing throughout with sparks on top, not as darkness with points in it.
var glow = 0.15

// Golden-ratio conjugate: an irrational step between adjacent pixels in noise
// space, so neighbours decorrelate without landing on the integer lattice.
var PIXEL_STEP = 0.6180339
// Stretch factor applied around the noise midpoint to use more of the 0..1 range.
var CONTRAST = 1.6
// A warm sun yellow, a little past pure yellow toward gold.
var HUE_SUN = 0.13
// Saturation at a spark's peak. Not quite 0, so the brightest points stay warm
// white rather than going clinically blue-white.
var PEAK_SAT = 0.08

var t = 0

// How many pixels are sparkling at once
export function sliderDensity(v) { density = mix(0.05, 0.85, v) }
// How fast each spark swells and fades
export function sliderSpeed(v) { speed = mix(0.05, 2.5, v) }
// Brightness of the warm glow between sparks
export function sliderGlow(v) { glow = v * 0.25 }

export function beforeRender(delta) {
  // Perlin wraps every 256 units, so t can grow without a discontinuity.
  t += delta / 1000 * speed
}

export function render(index) {
  // perlin() returns roughly -1..1, bunched around 0.
  n = perlin(index * PIXEL_STEP, t, 0, 0)
  n = clamp(n * CONTRAST, -1, 1)
  n = (n + 1) / 2

  // Light only the top `density` share, eased in rather than switched on.
  v = smoothstep(1 - density, 1, n)
  v = v * v
  v = max(v, glow)

  // Saturated gold when dim, whitening as the spark peaks.
  hsv(HUE_SUN, mix(1, PEAK_SAT, v * v), v)
}
