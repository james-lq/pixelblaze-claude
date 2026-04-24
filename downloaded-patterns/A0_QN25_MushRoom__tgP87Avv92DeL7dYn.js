// Pattern: A0 QN25 MushRoom
// ID: tgP87Avv92DeL7dYn

//
// TODOs:
//
// - Implement a smoother transition between idle and active
// -- maybe via detecting initial `energyAverage` bumps before going to "full kitty enable"?
//

/*
  Based on public pattern: Sound - spectroblots 1D/2D/3D
*/

var C_OBELISK_LENGTH = 370;
var C_SHROOM1_START = C_OBELISK_LENGTH;
var C_SHROOM1_LENGTH = 50;
var C_SHROOM2_START = C_SHROOM1_START + C_SHROOM1_LENGTH;
var C_SHROOM2_LENGTH = 50;

//
// These vars are set by the external sensor board, if one is connected. We
// don't actually use light readings in this pattern, so if the `light` value
// remains -1, no sensor board is connected. If connected, the sensor board sets
// the 32 frequencyData array elements according to sensed spectrum energy.
//
export var light = -1;
export var frequencyData = array(32);
export var energyAverage = 0;
export var maxFrequency = -1;
export var maxFrequencyMagnitude = -1;

export var ___toggleAggroMode = false;
export function toggleAggroMode(isEnabled) {
  ___toggleAggroMode = isEnabled;
}

export var ___reactiveMode = false;
export function toggleReactiveMode(isEnabled) {
  ___reactiveMode = isEnabled;
}

export var _sliderIdleBrightness = 1.0;
export function sliderIdleBrightness(value) {
  _sliderIdleBrightness = value;
}

export var __crystalH = 0.9;
export var __crystalS = 1.0;
export var __crystalV = 1.0;
export function hsvPickerCrystal(h, s, v) {
  __crystalH = h;
  __crystalS = s;
  __crystalV = v;
}

export var _sliderCrystalBrightness = 1.0;
export function sliderCrystalBrightness(value) {
  _sliderCrystalBrightness = value;
}

export var _sliderShroomBrightnessBoost = 0.2;
export function sliderShroomBrightnessBoost(value) {
  _sliderShroomBrightnessBoost = value;
}

// Set to true to inject simulated sound
export var aaaSimulateSound = false;
export function toggleSimulateSound(isEnabled) {
  aaaSimulateSound = isEnabled;

  // Set a fake energyAverage value since that's the easiest way to "enable the kitty".
  // In the presence of a real sensor board, the global value will be auto-refreshed.
  energyAverage = isEnabled ? 1 : 0;
}

// Set to true to simulate pixel mapping via coordinate spoofing
export var aaaSimulatePixelMapping = true;
export function toggleSimulatePixelMapping(isEnabled) {
  aaaSimulatePixelMapping = isEnabled;
}

export function showNumberEnergyAverage() {
  return energyAverage;
}

//
// These variables control the character of the visualization itself
//
averageWindowMs = 5000; // Compare spectrum energy to it's avg over this period
fade = 0.2; // What percentage of the pixel's brightness is retained each frame
speed = 0.3; // Speed of viewport travel through the spectrum field
target = 0.2; // Seek a sensitivity that makes this the average audio bucket level

export var pic = makePIController(10, 0.2, 450, 0, 600);
export var sensitivity = 0;
export var feedback = 0;
vals = array(32);
var averages = array(32);
pixels = array(pixelCount);
var scale;

export function gaugeFeedback() {
  return feedback;
}

export function gaugeGain() {
  return sensitivity / 100;
}

export function gaugeComplexity() {
  return scale / 1.3;
}

// Makes a new PI Controller
function makePIController(kp, ki, start, min, max) {
  var pic = array(5);
  pic[0] = kp;
  pic[1] = ki;
  pic[2] = start;
  pic[3] = min;
  pic[4] = max;
  return pic;
}

function calcPIController(pic, err) {
  pic[2] = clamp(pic[2] + err, pic[3], pic[4]);
  return max(pic[0] * err + pic[1] * pic[2], 0.3);
}

export var dw;
export function beforeRender(delta) {
  ___reactiveMode = false;

  idleSequenceTime = time(0.1);

  var v;
  t1 = time((30 / 65.536) * speed);

  zmorph = time((5000 / 65.536) * speed) * 256;

  resetTransform();
  translate3D(-0.5, -0.5, -0.5);
  scale = 0.15 * 2 + 0.5 * 2 * wave(time((40 / 65.536) * speed));
  if (nodeId() == 1) scale = 0.7;
  scale3D(scale, scale, scale);

  if (aaaSimulateSound) {
    doAt(40, delta, simulateSound);
  }

  dw = 1 - pow(0.98, delta / 100);
  // dw = delta / averageWindowMs

  sensitivity = calcPIController(pic, target - feedback);
  sensitivity = 50;
  feedback = 0;
  for (i = 0; i < 32; i++) {
    averages[i] = max(
      0.00001,
      averages[i] * (1 - dw) + frequencyData[i] * dw * sensitivity,
    );

    v =
      (frequencyData[i] * sensitivity - 4 * averages[i]) *
      10 *
      (0.2 + averages[i] * 100);
    vals[i] = clamp(vals[i] * 0.5 + v * 0.5, 0, 20);

    feedback += max(0, vals[i]);
  }
  feedback /= 32;

  frameFade = pow(fade, delta / 100);
  frameFadeM = 1 - frameFade;
}

// Calculate a "spoofed" x coordinate to simulate 3 separate 1D pixel map sections corresponding
// to the 3 physical strips we have.
function spoofXCoordinate(index) {
  if (index < C_SHROOM1_START) // Obelisk
  {
    return index / (C_SHROOM1_START - 1);
  } else if (index < C_SHROOM2_START) {
    return (index - C_SHROOM1_START) / C_SHROOM1_LENGTH;
  } else // Shroom 2 fills rest of possible indices
  {
    return (index - C_SHROOM2_START) / C_SHROOM2_LENGTH;
  }
}

// Render the idle sequence.
export var idleSequenceTime = -1;
function renderIdleHueCycler(index, x) {
  // TODO Set obelisk to static
  if (false) //index < C_SHROOM1_START)
  {
    hsv(__crystalH, __crystalS, __crystalV);
    return;
  }

  if (___toggleAggroMode) {
    idleSequenceTime = -10;
  }

  h = idleSequenceTime + x;
  s = 1;
  v = 1 * _sliderIdleBrightness;
  hsv(h, s, v);
}

// The fundamental rendering happens in 3D space, but will be projected down
// into lower dimensions for 2D matrices or 1D strips
export function render3D(index, x, y, z) {
  var i, h, s, v;

  x = abs(x); //cheap symetry

  // perlinFbm(x, y, z, lacunarity, gain, octaves)
  // Generate 3D fractal Perlin noise (fractial Brownian Motion).
  // The values will repeat every 256 or as specified with setPerlinWrap(), and can seamlessly wrap.
  // The lacunarity controls the distance between octaves and should be set to 2 or another integer value if wrapping is desired.
  // The gain controls the strength between each octave, try values around 0.5-0.8.
  p = triangle(perlinFbm(x, y, z + zmorph, 2, 1, 2));
  v = vals[p * 31];
  // v = v * v

  //fade stored pixel, add v, store, back to v
  v = pixels[index] = pixels[index] * frameFade + v * frameFadeM;
  h = p + t1;
  s = 4.5 - v;

  v = min(v, 1); //prevent overflow
  v = v * v; // Gamma-correction (or so they say?)
  v = v * _sliderCrystalBrightness;

  // All shroom LEDs get a brightness boost to generally keep the room a bit brighter.
  if (index > C_SHROOM1_START)
    v = clamp(v + _sliderShroomBrightnessBoost, 0, 1);

  hsv(h, s, v);
}

// Support 2D pixel mapped configurations
export function render2D(index, x, y) {
  render3D(index, x, y, 0);
}

/*
  This pixel mapper shim provides support for 1D strips and unmapped 2D matrices
  by calculating x & y assuming a 2D LED matrix display, given a matrix width
  and height.
*/
export function render(index, x) {
  if (aaaSimulatePixelMapping) {
    x = spoofXCoordinate(index);
  }

  if (___reactiveMode) render3D(index, x, 0, 0);
  else renderIdleHueCycler(index, x);
}

// doAt calls a function `fn` at a specified frequency, given ms elapsed `delta`
// For example, simulate sensor board data updates at 40Hz.
export var accumDelta = 0;

function doAt(hertz, delta, fn) {
  accumDelta += delta; // Accumulated miliseconds
  if (accumDelta <= 1000 / hertz) {
    return; // Do nothing
  } else {
    accumDelta -= 1000 / hertz; // Assumes `delta < 1000 / hertz`` on average
    fn(); // Call the passed-in function
  }
}

/*
  Simulate the sensor board variables used in this pattern, if no senor board is
  detected. The values and waveforms were chosen to approximate the look when
  real sound is sensed for a basic 4-on-the-floor loop.
*/
BPM = 120;
var measurePeriod = (4 * 60) / BPM / 65.536;

function simulateSound() {
  // Set a fake energyAverage value since that's the easiest way to "enable the kitty".
  // In the presence of a real sensor board, the global value will be auto-refreshed,
  // thus we need to force it to 1 here on every simulate call.
  energyAverage = 1;

  tM = time(measurePeriod); // 2 seconds per measure @120 BPM
  tP = time(8 * measurePeriod); // 8 measures per phrase
  for (i = 0; i < 32; i++) frequencyData[i] = 0;

  beat = (-4 * tM + 5) % 1; // 4 attacks per measure
  beat *= 0.02 * pow(beat, 4); // Scale magnitute and make concave-up
  // Splay energy out, most energy at lowest frequency bins
  for (i = 0; i < 10; i++) frequencyData[i] += (beat * (10 - i)) / 10;

  claps = 0.006 * square(2 * tM - 0.5, 0.1); // "&" of every beat
  for (i = 9; i < 14 + random(5); i++)
    frequencyData[i] += claps * (0.7 + 0.6 * random(i % 2));

  highHat = 0.01 * square(4 * tM - 0.5, 0.05); // Beats 2 and 4
  for (i = 18; i < 20; i++) frequencyData[i] += highHat * (0.8 + random(0.4));

  lead = 4 + floor(16 * wander(tP)); // Wandering fundamental synth's freq bin
  for (i = 4; i < 20; i++)
    // Excite the fundamental and, 40% of the time, 4 bins up
    frequencyData[i] += 0.005 * (lead == i || lead == (i - 4) * r(0.4));
}

// Random-ish perlin-esque walk for t in 0..1, outputs 0..1
// https://www.desmos.com/calculator/enggm6rcrm
function wander(t) {
  t *= 49.261; // Selected so t's wraparound will have continuous output
  return (wave(t / 2) * wave(t / 3) * wave(t / 5) + wave(t / 7)) / 2;
}

function r(p) {
  return random(1) < p;
} // Randomly true with probability p
