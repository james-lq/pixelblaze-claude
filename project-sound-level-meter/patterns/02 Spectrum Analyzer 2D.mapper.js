// Pixel map for project-sound-level-meter
//
// 8×12 grid: two WS2811 strings of 50 LEDs each (48 active + 2 unused per string).
// Each string zig-zags through 4 vertical columns of 12 LEDs.
// Physical spacing: 7" between pixels horizontally and vertically.
//
// Wiring:
//   String 0 (pixels 0–49):  columns 0–3 (low frequencies)
//   String 1 (pixels 50–99): columns 4–7 (high frequencies)
//   Even columns (0,2,4,6): wire bottom-to-top (pixel 0 = physical bottom)
//   Odd columns  (1,3,5,7): wire top-to-bottom (pixel 0 = physical top)
//
// IMPORTANT: In the Mapper tab, set scaling mode to "Fill" (not "Contain").
// This scales x and y independently so both axes map cleanly to 0..1.

function (pixelCount) {
  var map = []
  var i, string, localIdx, colInString, rowInCol, col, x, y

  for (i = 0; i < pixelCount; i++) {
    string   = Math.floor(i / 50)
    localIdx = i % 50

    // Pixels 48–49 of each string are unused (beyond the 4×12 active grid).
    // Place them at the last-used position so they don't expand the bounding box.
    if (localIdx >= 48) {
      col = string * 4 + 3   // last column of this string
      map.push([col * 7, 77])
      continue
    }

    colInString = Math.floor(localIdx / 12)   // 0–3 within this string
    rowInCol    = localIdx % 12               // 0–11 within this column
    col         = string * 4 + colInString    // 0–7 global column index
    x           = col * 7                     // inches: 0, 7, 14, 21, 28, 35, 42, 49

    // Even columns wire bottom-to-top: row 0 is at the physical bottom (y=77").
    // Odd  columns wire top-to-bottom: row 0 is at the physical top    (y=0").
    if (colInString % 2 === 0) {
      y = (11 - rowInCol) * 7    // row 0 → y=77" (bottom), row 11 → y=0" (top)
    } else {
      y = rowInCol * 7           // row 0 → y=0"  (top),    row 11 → y=77" (bottom)
    }

    map.push([x, y])
  }

  return map
}
