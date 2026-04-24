// Pattern: AAAA SWITCHTEST
// ID: tJSkQRyTWcA8JcXPG

export var _time_1s_saw = 0;
export var _time_1s_saw_prev = 99; // Init to high value so first second always counted
export var _time_secs_since_boot = 0;
function handle_time() {
  // time() returns a built-in provides a normalized "waveform of time", 0.015 means it rolls over to 1.0 every second
  _time_1s_saw = time(0.015);
  if (_time_1s_saw < _time_1s_saw_prev) {
    _time_secs_since_boot++;
  }
  _time_1s_saw_prev = _time_1s_saw;
}

var BUTTON_PIN = 26;
pinMode(BUTTON_PIN, INPUT_PULLUP);

export var _switchOn = false;
function handle_DIO() {
  _switchOn = !digitalRead(BUTTON_PIN);
}

pixels = array(pixelCount);
pixels.mutate((v, i, a) => 0);

export function beforeRender(delta) {
  handle_time();
  handle_DIO();

  if (_switchOn) {
    pixels.mutate((v, i, a) => 0.5);
  } else {
    pixels.mutate((v, i, a) => 0);
  }
}

export function render(index) {
  v = pixels[index];
  rgb(v, v, v);
}
