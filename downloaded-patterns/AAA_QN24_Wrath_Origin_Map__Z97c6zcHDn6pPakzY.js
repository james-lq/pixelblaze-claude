// Pattern: AAA QN24 Wrath Origin Map
// ID: Z97c6zcHDn6pPakzY

export var actualState;
actualState = STATE_INIT;
var oneTimeInitComplete = false;

//
// STATES
//

STATE_HANDLERS = [
  handle_STATE_INIT,

  handle_STATE_DEBUG_PAUSED,
  handle_STATE_DEBUG_ALL,
  handle_STATE_DEBUG_SINGLE,

  handle_STATE_IDLE,
  handle_STATE_E00_TICKTOCK,
  handle_STATE_E01_FOREST,
  handle_STATE_E02_TICKTOCK,
  handle_STATE_E03_NW_MINE,
  handle_STATE_E04_TICKTOCK,
  handle_STATE_E05_SAILORS,
  handle_STATE_E06_TICKTOCK,
  handle_STATE_E07_NW_MINE,
  handle_STATE_E08_NW_MINE_WINGS,
  handle_STATE_E09_STORMS,
  handle_STATE_E10_TICKTOCK,
  handle_STATE_E11_SW_MINE,
  handle_STATE_E12_TICKTOCK,
  handle_STATE_E13_CEN_MINE,
  handle_STATE_E14_TREMOR,
  handle_STATE_E15_TICKTOCK,
  handle_STATE_E16_CEN_MINE_MORE,
  handle_STATE_E17_EARTHQUAKE,
  handle_STATE_E18_TICKTOCK_FAST,
  handle_STATE_E19_MINE_MINE_MINE,
  handle_STATE_E20_FLIGHT,
  handle_STATE_E21_ERUPTION,
];

STATE_SENTINEL = STATE_HANDLERS.length - 1;

state_times_start = array(STATE_HANDLERS.length);
state_times_start.mutate((v, i, a) => -1);

state_times_elapsed = array(STATE_HANDLERS.length);
state_times_elapsed.mutate((v, i, a) => -1);

STATE_TIMES_EVENT_DURATIONS = array(STATE_HANDLERS.length);
STATE_TIMES_EVENT_DURATIONS.mutate((v, i, a) => -1);

STATE_INIT = 0;

STATE_DEBUG_PAUSED = 1;
STATE_DEBUG_ALL = 2;
STATE_DEBUG_SINGLE = 3;

STATE_IDLE = 4;

STATE_E00_TICKTOCK = 5;
STATE_TIMES_EVENT_DURATIONS[STATE_E00_TICKTOCK] = 5;

STATE_E01_FOREST = 6;
STATE_TIMES_EVENT_DURATIONS[STATE_E01_FOREST] = 4;

STATE_E02_TICKTOCK = 7;
STATE_TIMES_EVENT_DURATIONS[STATE_E02_TICKTOCK] = 5;

STATE_E03_NW_MINE = 8;
STATE_TIMES_EVENT_DURATIONS[STATE_E03_NW_MINE] = 7;

STATE_E04_TICKTOCK = 9;
STATE_TIMES_EVENT_DURATIONS[STATE_E04_TICKTOCK] = 5;

STATE_E05_SAILORS = 10;
STATE_TIMES_EVENT_DURATIONS[STATE_E05_SAILORS] = 5;

STATE_E06_TICKTOCK = 11;
STATE_TIMES_EVENT_DURATIONS[STATE_E06_TICKTOCK] = 5;

STATE_E07_NW_MINE = 12;
STATE_TIMES_EVENT_DURATIONS[STATE_E07_NW_MINE] = 11;

STATE_E08_NW_MINE_WINGS = 13;
STATE_TIMES_EVENT_DURATIONS[STATE_E08_NW_MINE_WINGS] = 7;

STATE_E09_STORMS = 14;
STATE_TIMES_EVENT_DURATIONS[STATE_E09_STORMS] = 15;

STATE_E10_TICKTOCK = 15;
STATE_TIMES_EVENT_DURATIONS[STATE_E10_TICKTOCK] = 5;

STATE_E11_SW_MINE = 16;
STATE_TIMES_EVENT_DURATIONS[STATE_E11_SW_MINE] = 10;

STATE_E12_TICKTOCK = 17;
STATE_TIMES_EVENT_DURATIONS[STATE_E12_TICKTOCK] = 5;

STATE_E13_CEN_MINE = 18;
STATE_TIMES_EVENT_DURATIONS[STATE_E13_CEN_MINE] = 10;

STATE_E14_TREMOR = 19;
STATE_TIMES_EVENT_DURATIONS[STATE_E14_TREMOR] = 7;

STATE_E15_TICKTOCK = 20;
STATE_TIMES_EVENT_DURATIONS[STATE_E15_TICKTOCK] = 5;

STATE_E16_CEN_MINE_MORE = 21;
STATE_TIMES_EVENT_DURATIONS[STATE_E16_CEN_MINE_MORE] = 30; // 6 DayRing advances @ 5 seconds

STATE_E17_EARTHQUAKE = 22;
STATE_TIMES_EVENT_DURATIONS[STATE_E17_EARTHQUAKE] = 9;

STATE_E18_TICKTOCK_FAST = 23;
STATE_TIMES_EVENT_DURATIONS[STATE_E18_TICKTOCK_FAST] = 10;

STATE_E19_MINE_MINE_MINE = 24;
STATE_TIMES_EVENT_DURATIONS[STATE_E19_MINE_MINE_MINE] = 13;

STATE_E20_FLIGHT = 25;
STATE_TIMES_EVENT_DURATIONS[STATE_E20_FLIGHT] = 8;

STATE_E21_ERUPTION = 26;
STATE_TIMES_EVENT_DURATIONS[STATE_E21_ERUPTION] = 12;

/**
STATE_XXXXXXXXXXX   = 99;
STATE_TIMES_EVENT_DURATIONS[STATE_XXXXXXXXXXX]  = 99;

STATE_E00_TICKTOCK
0:05

STATE_E01_FOREST
0:04
STATE_E02_TICKTOCK
0:05

STATE_E03_NW_MINE
0:07
STATE_E04_TICKTOCK
0:05

STATE_E05_SAILORS
0:05
STATE_E06_TICKTOCK
0:05
STATE_E07_NW_MINE
0:11
STATE_E08_NW_MINE_WINGS
0:07
STATE_E09_STORMS
0:15

STATE_E10_TICKTOCK
0:05

STATE_E11_SW_MINE
0:10
STATE_E12_TICKTOCK
0:05
STATE_E13_CEN_MINE
0:10
STATE_E14_TREMOR
0:07
STATE_E15_TICKTOCK
0:05

STATE_E16_CEN_MINE_MORE // 6 intervals, 5 dongs
0:05
0:05
0:05
0:05
0:05
0:05

STATE_E17_EARTHQUAKE
0:09
STATE_E18_TICKTOCK_FAST
0:10

STATE_E19_MINE_MINE_MINE
0:13

STATE_E20_FLIGHT
0:08
STATE_E21_ERUPTION
0:12
 
**/

pixels = array(pixelCount);
pixelsHue = array(pixelCount);

// TODO Revisit naive hue init...
// For now, set all even pixels to warm color, except those on the island.
pixels_setDayRingDefaultColors();
array_setRange(pixelsHue, 0.5, 0, 49);

function pixels_setDayRingDefaultColors() {
  pixelsHue.mutate((v, i, a) => (i >= 50 && i % 2 ? 0.5 : 0.25));
}

function pixels_setDayRingStormColors() {
  array_setRange(pixelsHue, 0, 50, 99);
}

//
// State vars: IO and Time
//
export var buttonValue;
var BUTTON_PIN = 26;
pinMode(BUTTON_PIN, INPUT_PULLDOWN);

export var _time_1s_saw = 0;
export var _time_1s_saw_prev = 99; // Init to high value so first second always counted
export var _time_1s_since_boot = 0;

export var time_currentSecond;
export var time_currentMinute; // For quick sanity check display
export var time_second_prev;
time_second_prev = -1;
export var time_second_start;
time_second_start = -1;

export var time_seconds_since_boot;
time_seconds_since_boot = -1;

export var zzzStartHour;
zzzStartHour = clockHour();
export var zzzStartMinute;
zzzStartMinute = clockMinute();
export var zzzStartSecond;
zzzStartSecond = clockSecond();

export var debugStartIdleState;
debugStartIdleState = false;

debugSinglePixelIndex = 50;
// UNUSED DAYRING PIXELS: 96, 98

function handle_STATE_INIT() {
  if (oneTimeInitComplete) {
    updateEventTimeElapsed(STATE_INIT);
    return;
  }

  startEvent(STATE_INIT);

  pixels.mutate((v, i, a) => 0);

  oneTimeInitComplete = true;
}

function handle_STATE_IDLE() {
  if (overrideToDebugState()) {
    return;
  }

  var localCurrentEventId = STATE_IDLE;
  updateEventTimeElapsed(localCurrentEventId);

  // Concept: Simple slow timewave.
  t = time(0.06);
  tWave = wave(t);
  // pixels.mutate((v, i, a) => (t + i/pixelCount) / 2);
  pixels.mutate((v, i, a) => (i >= 50 ? tWave * 0.3 : 0));

  // TODO Concept: Idle pattern is a generalization of advancing the clock.
  // localElapsed = getEventTimeElapsed(STATE_IDLE);
  // pixels_advanceDayRing(localElapsed, 5, 50, 50);
}

function handle_STATE_E00_TICKTOCK() {
  localIsDone = events_doStandardPreamble(STATE_E00_TICKTOCK, STATE_E01_FOREST);
  if (localIsDone) {
    return;
  }

  localElapsed = getEventTimeElapsed(STATE_E00_TICKTOCK);
  localDuration = getEventTimeDuration(STATE_E00_TICKTOCK);
  pixels_advanceDayRing(localElapsed, localDuration, 50, 5);
}

function handle_STATE_E01_FOREST() {
  localIsDone = events_doStandardPreamble(STATE_E01_FOREST, STATE_E02_TICKTOCK);
  if (localIsDone) {
    pixels_clearIsland();
    return;
  }

  pixels_clearIsland();
  pixels[14] = 1;
  pixels[15] = 1;
}

function handle_STATE_E02_TICKTOCK() {
  events_doStandardTickTock(STATE_E02_TICKTOCK, STATE_E03_NW_MINE, 55, 4); // To 59
  // localIsDone = events_doStandardPreamble(STATE_E02_TICKTOCK, STATE_E03_NW_MINE);
  // if(localIsDone) { return; }

  // localElapsed = getEventTimeElapsed(STATE_E02_TICKTOCK);
  // localDuration = getEventTimeDuration(STATE_E02_TICKTOCK);
  // pixels_advanceDayRing(localElapsed, localDuration, 55, 4);
}

function handle_STATE_E03_NW_MINE() {
  localIsDone = events_doStandardPreamble(
    STATE_E03_NW_MINE,
    STATE_E04_TICKTOCK,
  );
  if (localIsDone) {
    pixels_clearIsland();
    return;
  }

  pixels_clearIsland();
  pixels[11] = 1;
}

function handle_STATE_E04_TICKTOCK() {
  events_doStandardTickTock(STATE_E04_TICKTOCK, STATE_E05_SAILORS, 59, 3); // To 62
}

function handle_STATE_E05_SAILORS() {
  localIsDone = events_doStandardPreamble(
    STATE_E05_SAILORS,
    STATE_E06_TICKTOCK,
  );
  if (localIsDone) {
    pixels_clearIsland();
    return;
  }

  pixels_clearIsland();
  array_setRange(pixels, 1, 26, 28);
}

function handle_STATE_E06_TICKTOCK() {
  events_doStandardTickTock(STATE_E06_TICKTOCK, STATE_E07_NW_MINE, 62, 2); // To 64
}

function handle_STATE_E07_NW_MINE() {
  localIsDone = events_doStandardPreamble(
    STATE_E07_NW_MINE,
    STATE_E08_NW_MINE_WINGS,
  );
  if (localIsDone) {
    pixels_clearIsland();
    return;
  }

  pixels_clearIsland();
  pixels[11] = 1;
}

function handle_STATE_E08_NW_MINE_WINGS() {
  localIsDone = events_doStandardPreamble(
    STATE_E08_NW_MINE_WINGS,
    STATE_E09_STORMS,
  );
  if (localIsDone) {
    pixels_clearIsland();
    return;
  }

  pixels_clearIsland();
  pixels[12] = 1;
}

// Add a slider control to select the speed of the lightning bolts
storm_fade = 15; // How fast each lightning bolt section fades out
storm_delayFactor = 15; // Determines the time between successive bolt segments
storm_resetDelayFactor = 1000; // Determines the pause between complete lightning bolts

// _v from the slider will be in 0..1
// export function sliderBoltSpeed(_v) {
//   fade = 2 + _v * 13 // fade will therefore be set to something between 2 and 15
//   delayFactor = 15 + (1 - _v) * 15
//   resetDelayFactor = 1000 + (1 - _v) * 2000
// }

// Set up each bolt segment to be between 1/15th and 1/6th of the strip length
storm_boltMin = floor(pixelCount / 15);
storm_boltMax = ceil(pixelCount / 6);

storm_x = 0;
storm_timer = 0;

// TODO P1 Un-hack the override of saturation to zero as well for the storm
_storm_active = false;

function handle_STATE_E09_STORMS() {
  localIsDone = events_doStandardPreamble(STATE_E09_STORMS, STATE_E10_TICKTOCK);
  if (localIsDone) {
    _storm_active = false;
    pixels_clearIsland();
    pixels_clearDayRing();
    pixels_setDayRingDefaultColors();
    return;
  }

  _storm_active = true;
  pixels_setDayRingStormColors();

  // Most frames we are fading all pixels and counting down a timer
  for (i = 0; i < pixelCount; i++)
    pixels[i] -= pixels[i] * storm_fade * (_delta / 1000) + (1 >> 16);

  // `timer` is the ms remaining before we ignite a new lightning bolt section
  storm_timer -= _delta;

  if (storm_timer <= 0) {
    // New lightning bolt segment's size, in pixels
    boltSize = storm_boltMin + random(storm_boltMax - storm_boltMin);
    while (boltSize-- > 0 && storm_x < pixelCount) {
      pixels[storm_x++] = 1; // Fill these pixels bright white
    }

    storm_timer = random(storm_delayFactor) + storm_delayFactor / 5;
    // Squaring makes longer delays, and makes them rarer. A delayFactor of 15
    // produces 9ms-324ms timers between successive bolt segments igniting.
    storm_timer *= storm_timer;

    // If a lightning bolt has reached the end of the strip,
    if (storm_x >= pixelCount) {
      storm_x = 0;
      // Pause between bolts for 0.33-1.33 * resetDelayFactor milliseconds
      storm_timer = random(storm_resetDelayFactor) + storm_resetDelayFactor / 3;
    }
  }

  // Quick hack to keep the island lights hidden to avoid spoilers.
  pixels_clearIsland();
}

function handle_STATE_E10_TICKTOCK() {
  events_doStandardTickTock(STATE_E10_TICKTOCK, STATE_E11_SW_MINE, 69, 3); // To 72
}

function handle_STATE_E11_SW_MINE() {
  localIsDone = events_doStandardPreamble(
    STATE_E11_SW_MINE,
    STATE_E12_TICKTOCK,
  );
  if (localIsDone) {
    pixels_clearIsland();
    return;
  }

  pixels_clearIsland();
  pixels[30] = 1;
}

function handle_STATE_E12_TICKTOCK() {
  events_doStandardTickTock(STATE_E12_TICKTOCK, STATE_E13_CEN_MINE, 73, 1); // To 74
}

function handle_STATE_E13_CEN_MINE() {
  localIsDone = events_doStandardPreamble(STATE_E13_CEN_MINE, STATE_E14_TREMOR);
  if (localIsDone) {
    pixels_clearIsland();
    return;
  }

  pixels_clearIsland();
  pixels[17] = 1;
  pixels[18] = 1;
}

function handle_STATE_E14_TREMOR() {
  localIsDone = events_doStandardPreamble(STATE_E14_TREMOR, STATE_E15_TICKTOCK);
  if (localIsDone) {
    pixels_clearIsland();
    return;
  }

  pixels_clearIsland();
  pixels[21] = 1;
}

function handle_STATE_E15_TICKTOCK() {
  events_doStandardTickTock(STATE_E15_TICKTOCK, STATE_E16_CEN_MINE_MORE, 76, 2); // To 78
}

function handle_STATE_E16_CEN_MINE_MORE() {
  localIsDone = events_doStandardPreamble(
    STATE_E16_CEN_MINE_MORE,
    STATE_E17_EARTHQUAKE,
  );
  if (localIsDone) {
    pixels_clearIsland();
    return;
  }

  pixels_clearIsland();
  pixels[16] = 1;
  pixels[17] = 1;
}

function handle_STATE_E17_EARTHQUAKE() {
  localIsDone = events_doStandardPreamble(
    STATE_E17_EARTHQUAKE,
    STATE_E18_TICKTOCK_FAST,
  );
  if (localIsDone) {
    pixels_clearIsland();
    return;
  }

  pixels_clearIsland();
  pixels[19] = 1;
  pixels[20] = 1;
  pixels[21] = 1;
}

function handle_STATE_E18_TICKTOCK_FAST() {
  events_doStandardTickTock(
    STATE_E18_TICKTOCK_FAST,
    STATE_E19_MINE_MINE_MINE,
    85,
    7,
  ); // To 92
}

function handle_STATE_E19_MINE_MINE_MINE() {
  localIsDone = events_doStandardPreamble(
    STATE_E19_MINE_MINE_MINE,
    STATE_E20_FLIGHT,
  );
  if (localIsDone) {
    pixels_clearIsland();
    return;
  }

  pixels_clearIsland();
  pixels[16] = 1;
  pixels[17] = 1;
}

function handle_STATE_E20_FLIGHT() {
  current = STATE_E20_FLIGHT;
  next = STATE_E21_ERUPTION;
  localIsDone = events_doStandardPreamble(current, next);
  if (localIsDone) {
    pixels_clearIsland();
    return;
  }

  localElapsed = getEventTimeElapsed(current);
  localDuration = getEventTimeDuration(next);
  localSecondsPerFlap = round(localDuration / 4);

  if (localElapsed < localSecondsPerFlap) {
    pixels_clearIsland();
    pixels[18] = 1;
  } else if (localElapsed < localSecondsPerFlap * 2) {
    pixels_clearIsland();
    pixels[22] = 1;
  } else if (localElapsed < localSecondsPerFlap * 3) {
    pixels_clearIsland();
    pixels[32] = 1;
  } else if (localElapsed < localSecondsPerFlap * 4) {
    pixels_clearIsland();
    pixels[33] = 1;
  }
}

function handle_STATE_E21_ERUPTION() {
  current = STATE_E21_ERUPTION;
  next = STATE_IDLE;
  localIsDone = events_doStandardPreamble(current, next);
  if (localIsDone) {
    pixels_clearIsland();
    return;
  }

  array_setRange(pixels, 1, 33, 48);
  // 33-48
}

function handle_STATE_DEBUG_PAUSED() {
  // NOOP
}

function handle_STATE_DEBUG_ALL() {
  pixels.mutate((v, i, a) => 1);
}

function handle_STATE_DEBUG_SINGLE() {
  pixels.mutate((v, i, a) => (i == debugSinglePixelIndex ? 1 : 0));
}

function pixels_advanceDayRing(elapsed, duration, start, pixelsToAdvance) {
  // TODO: Alternate color sun/moon
  localTimePerPixel = duration / pixelsToAdvance;
  localDayPixel = floor(elapsed / localTimePerPixel) + start;
  pixels_clearDayRing();
  pixels[localDayPixel] = 1;
}

function pixels_clearIsland() {
  array_setRange(pixels, 0, 0, 50);
}

function pixels_clearDayRing() {
  array_setRange(pixels, 0, 50, 99);
}

function array_setRange(array, value, start, end) {
  for (i = start; i <= end; i++) {
    array[i] = value;
  }
}

//
// Event Time Bookkeeping
// TODO P2 Refactor event time bookkeeping to be relative to Event Zero, otherwise we have to deal with second count overflow at ~9 hours
//
export var _unsafeState;
_unsafeState = -1;
function safeStateId(state) {
  // TODO Set a debug flag var if this EVER actually triggers
  _unsafeState = state;

  // Protect against dumb mistakes...
  clampedState = clamp(state, 0, STATE_SENTINEL);
  // Protect against apparent serialization glitches that can load fractional numbers
  clampedState = floor(clampedState);

  return clampedState;
}

function startEvent(state) {
  actualState = safeStateId(state);
  state_times_start[actualState] = time_seconds_since_boot;
}

export var _currentEventDuration = -1;
export var _currentEventElapsed = -1;
function updateEventTimeElapsed(state) {
  var localState = safeStateId(state);

  _currentEventDuration = STATE_TIMES_EVENT_DURATIONS[localState];
  _currentEventElapsed =
    time_seconds_since_boot - state_times_start[localState];
  state_times_elapsed[localState] = _currentEventElapsed;
}

function events_doStandardPreamble(current, next) {
  if (overrideToDebugState()) {
    return true;
  }

  var localCurrent = safeStateId(current);
  var localNext = safeStateId(next);
  updateEventTimeElapsed(localCurrent);
  return events_advanceToNext(localCurrent, localNext);
}

function events_doStandardTickTock(current, next, startPixel, pixelsToAdvance) {
  localIsDone = events_doStandardPreamble(current, next);
  if (localIsDone) {
    return;
  }

  localElapsed = getEventTimeElapsed(current);
  localDuration = getEventTimeDuration(next);
  pixels_advanceDayRing(
    localElapsed,
    localDuration,
    startPixel,
    pixelsToAdvance,
  );
}

function events_advanceToNext(current, next) {
  var localCurrent = safeStateId(current);
  var localNext = safeStateId(next);
  if (getEventTimeElapsed(localCurrent) >= getEventTimeDuration(localCurrent)) {
    startEvent(localNext);
    return true;
  }

  return false;
}

function getEventTimeElapsed(state) {
  var localState = safeStateId(state);
  return state_times_elapsed[localState];
}

function getEventTimeDuration(state) {
  var localState = safeStateId(state);
  return STATE_TIMES_EVENT_DURATIONS[localState];
}

//
// GUI
//

export function showNumberActualState() {
  return actualState;
}

export function showNumberTimeSinceBoot() {
  return time_seconds_since_boot;
}

export function triggerDebugStartIdle() {
  debugStartIdleState = true;
}

export var debugStartEvent0;
debugStartEvent0 = false;
export function triggerDebugStartEvent0() {
  debugStartEvent0 = true;
}

export function toggleDebugMode(isEnabled) {
  if (!oneTimeInitComplete) {
    return;
  }

  if (isEnabled) {
    if (!debugModeEnabled) {
      startDebugMode();
    }
  } else {
    if (debugModeEnabled) {
      stopDebugMode();
    }
  }
}

export var debugModeEnabled;
var debugModeEnabled = false;
export var debugModePreviousState;
var debugModePreviousState = -1;
function startDebugMode() {
  debugModeEnabled = true;
  debugModePreviousState = actualState;
  startEvent(STATE_DEBUG_PAUSED);
}

function stopDebugMode() {
  debugModeEnabled = false;
  startEvent(debugModePreviousState);
}

function overrideToDebugState() {
  return debugModeEnabled;
}

export function inputNumberDebugState(v) {
  if (debugModeEnabled) {
    startEvent(v);
  }
}

export function inputNumberDebugSinglePixel(v) {
  debugSinglePixelIndex = v;
}

function DebugHandleTriggers() {
  if (debugStartIdleState) {
    startEvent(STATE_IDLE);
    debugStartIdleState = false;
  }

  if (debugStartEvent0) {
    startEvent(STATE_E00_TICKTOCK);
    debugStartEvent0 = false;
  }
}

//
// MAGIC!
//
export var _delta = 0;
export var _buttonStartTick = -1;
export var _buttonPressed = false;
export function beforeRender(delta) {
  _delta = delta;

  //
  // TIME CALCS
  //
  // Minute-based time not really needed, just handy for sanity-check while debugging
  time_currentMinute = clockMinute();
  time_currentSecond = clockSecond();

  if (time_second_prev != time_currentSecond) {
    time_seconds_since_boot++;
  }

  time_second_prev = time_currentSecond;

  // Alternative way to get a 1-second time:
  // time() returns a built-in provides a normalized "waveform of time", 0.015 means it rolls over to 1.0 every second
  _time_1s_saw = time(0.015);
  if (_time_1s_saw < _time_1s_saw_prev) {
    _time_1s_since_boot++;
  }
  _time_1s_saw_prev = _time_1s_saw;

  //
  // BUTTON HANDLER
  //
  buttonValue = digitalRead(BUTTON_PIN);
  // _buttonPressed = !buttonValue;
  // if(_buttonPressed && _buttonStartTick < 0)
  // {
  //   _buttonStartTick = time_seconds_since_boot;
  // }
  // else if (_buttonStartTick != time_seconds_since_boot && digitalRead(buttonValue))
  // {
  // }

  //
  // State Machine
  //
  var localState = safeStateId(actualState);
  STATE_HANDLERS[localState]();

  // Allow debug triggers to override next state.
  DebugHandleTriggers();
}

export function render(index) {
  localHue = pixelsHue[index];
  localSaturation = _storm_active ? 0 : 1;
  localValue = pixels[index];
  hsv(localHue, localSaturation, localValue);
}
