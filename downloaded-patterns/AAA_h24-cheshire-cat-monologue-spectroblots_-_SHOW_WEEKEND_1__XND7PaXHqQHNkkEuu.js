// Pattern: AAA h24-cheshire-cat-monologue-spectroblots - SHOW WEEKEND 1
// ID: XND7PaXHqQHNkkEuu

// CAT: 37 LEDs
// SHROOM1: 50 LEDs
// SHROOM2: 50 LEDs

/*
  Sound - spectroblots 1D/2D/3D

  This pattern is designed to use the sensor expansion board, but falls back to
  simulated sound data if the sensor board isn't detected.
  
  It also supports pixel mapped configurations with 2D or 3D maps. 

  This pattern uses the different frequencies in sound (e.g. bass vs mids vs
  treble) and compares the current reading for each of the 32 frequency bins to
  its running average. When the current reading is high, it's projected onto
  certain sections of the strip, matrix, or 3D space. 

*/

/*
  These vars are set by the external sensor board, if one is connected. We
  don't actually use light readings in this pattern, so if the `light` value
  remains -1, no sensor board is connected. If connected, the sensor board sets 
  the 32 frequencyData array elements according to sensed spectrum energy.
*/
export var light = -1;
export var frequencyData = array(32);

// These variables control the character of the visualization itself
averageWindowMs = 5000; // Compare spectrum energy to it's avg over this period
fade = 0.2; // What percentage of the pixel's brightness is retained each frame
speed = 0.3; // Speed of viewport travel through the spectrum field
target = 0.2; // Seek a sensitivity that makes this the average audio bucket level

export var pic = makePIController(10, 0.2, 450, 0, 600);
export var sensitivity = 0;
export var feedback = 0;
vals = array(32);
export var averages = array(32);
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
  var v;
  t1 = time((30 / 65.536) * speed);

  zmorph = time((5000 / 65.536) * speed) * 256;

  resetTransform();
  translate3D(-0.5, -0.5, -0.5);
  scale = 0.15 * 2 + 0.5 * 2 * wave(time((40 / 65.536) * speed));
  if (nodeId() == 1) scale = 0.7;
  scale3D(scale, scale, scale);

  // If no sensor board is attached, simulate sensor data at 40Hz
  if (light == -1) doAt(40, delta, simulateSound);

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

// The fundamental rendering happens in 3D space, but will be projected down
// into lower dimensions for 2D matrices or 1D strips
export function render3D(index, x, y, z) {
  var i, h, s, v;

  x = abs(x); //cheap symetry

  p = triangle(perlinFbm(x, y, z + zmorph, 2, 1, 2));
  v = vals[p * 31];
  // v = v * v

  //fade stored pixel, add v, store, back to v
  v = pixels[index] = pixels[index] * frameFade + v * frameFadeM;
  h = p + t1;
  s = 4.5 - v;

  v = min(v, 1); //prevent overflow
  hsv(h, s, v * v);
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
  render3D(index, x, 0, 0);
}

// doAt calls a function `fn` at a specified frequency, given ms elapsed `delta`
// For example, simulate sensor board data updates at 40Hz.
var accumDelta = 0;

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
