// Pattern: AAA QN24 Easy Mapper BUTTON TEST
// ID: r6orHJfdBa4QwAKLv

// Mode
// 0: Single-pixel
// 1: All-pixel
// 2: Cycle pixels
export var __debug_mode = 0;

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

export var _buttonPressed = false;
export var _buttonPressedStartTick = -1;
export var _buttonHeld1s = false;
export var _buttonFlag = false;
function handle_Button() {
  // If button is flagged but state not cleared, don't bother reading again.
  // if (_buttonFlag) { return; }

  _buttonPressed = !digitalRead(BUTTON_PIN);
  // if(_buttonPressed && _buttonPressedStartTick < 0)
  // {
  //   _buttonPressedStartTick = _time_secs_since_boot;
  // }
  // else if (_buttonPressedStartTick != _time_secs_since_boot && !digitalRead(BUTTON_PIN))
  // {
  //   _buttonFlag = true;
  // }
}

export function triggerAckButton() {
  _buttonFlag = false;
  _buttonPressedStartTick = -1;
}

pixels = array(pixelCount);

export var currentPixel;
currentPixel = 0;

//export var activePixels;

export function inputNumberPixel(v) {
  currentPixel = v;
}

export function inputNumberMode(v) {
  __debug_mode = v;
}

export function beforeRender(delta) {
  handle_time();
  handle_Button();

  currentDelta = delta;

  if ((__debug_mode = 0)) {
    pixels.mutate((v, i, a) => (i == currentPixel ? 1 : 0));
  } else if ((__debug_mode = 1)) {
    pixels.mutate((v, i, a) => 1);
  } else if ((__debug_mode = 2)) {
    pixels.mutate((v, i, a) => 0);
  }
}

export function render(index) {
  v = pixels[index];
  rgb(v, v, v);
}
