// Pattern: AAA QN24 Sandbox
// ID: cPvqSzbnXLz8jsauM

export var buttonValue;
var BUTTON_PIN = 26;
pinMode(BUTTON_PIN, INPUT_PULLDOWN);

export var time_currentSecond;
export var time_currentMinute; // For quick sanity check display
export var time_second_prev;
time_second_prev = -1;
export var time_second_start;
time_second_start = -1;

export var time_seconds_since_boot;
time_seconds_since_boot = -1;
export var time_seconds_since_start;
time_seconds_since_start = -1;

export var zzzStartHour;
zzzStartHour = clockHour();
export var zzzStartMinute;
zzzStartMinute = clockMinute();
export var zzzStartSecond;
zzzStartSecond = clockSecond();

pixels = array(pixelCount);

PIXELS_DAY_RING_COUNT = 48;
export var TIME_SECONDS_PER_YEAR;
TIME_SECONDS_PER_YEAR = 190; // 190 seconds in total active cycle.
export var TIME_SECONDS_PER_PIXEL;
TIME_SECONDS_PER_PIXEL = TIME_SECONDS_PER_YEAR / PIXELS_DAY_RING_COUNT;

PIXELS_RING_START = 50;

export var pixels_dayRingCurrent;
pixels_dayRingCurrent = -1;

export function beforeRender(delta) {
  //
  // TIME CALCS
  //
  // Minute-based time not really needed, just handy for sanity-check while debugging
  time_currentMinute = clockMinute();
  time_currentSecond = clockSecond();
  // Alternative way to get a 1-second time:
  // time() returns a built-in provides a normalized "waveform of time", 0.015 means it rolls over to 1.0 every second
  // timeValue = time(0.015)

  if (time_second_prev != time_currentSecond) {
    time_seconds_since_boot++;
  }

  time_second_prev = time_currentSecond;

  //
  // BUTTON HANDLER
  //
  buttonValue = digitalRead(BUTTON_PIN);

  // TODO: Replace emulated button-start with real logic
  if (time_second_start < 0 && time_seconds_since_boot > 10) {
    time_second_start = time_seconds_since_boot;
  }

  if (time_second_start > 0) {
    time_seconds_since_start = time_seconds_since_boot - time_second_start;
  }

  //
  // RENDER
  //

  pixels_dayRingCurrent = round(
    time_seconds_since_start / TIME_SECONDS_PER_PIXEL,
  );
  for (i = 0; i < pixelCount; i++) {
    if (i == pixels_dayRingCurrent + 50)
      pixels[i] = i % 2 ? [0, 0, 1] : [1, 1, 0]; // Days are yellow, nights are blue
    else pixels[i] = [0, 0, 0];
  }

  // for (i = 0; i < pixelCount; i++)
  // {
  //   pixels[i] = pixelRenderClockTick(i);
  // }

  // if (time_second_start < 0) // INACTIVE
  // {
  //   if (buttonValue == 0)
  //   {
  //     time_second_start = time_seconds_since_boot;
  //   }
  // }
  // else // ACTIVE
  // {
  //   day = (time_seconds_since_boot - time_second_start) / TIME_PER_DAY;
  //   if (day > TIME_DAYS)
  //   {
  //     time_second_start = -1;
  //     day = 0;
  //   }
  // }
}

export function render(index) {
  rgb(pixels[index][0], pixels[index][1], pixels[index][2]);
}

// export var zzz_time_clockTickIndex;
// function pixelRenderClockTick(index)
// {
//   zzz_time_clockTickIndex = PIXELS_RING_START + time_seconds_since_boot % 50;
//   if (index == zzz_time_clockTickIndex)
//   {
//     value = 1;
//   }
//   else
//   {
//     value = 0;
//   }

//   return value;
// }
