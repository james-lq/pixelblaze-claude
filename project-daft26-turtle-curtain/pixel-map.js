// Pixel map for project-daft26-turtle-curtain
//
// 50 LEDs arranged as 5 columns × 10 rows hanging from a bar.
// Each column is a single hanging strand of 10 pixels.
//
// Wiring (serpentine columns):
//   Pixel 0: upper-left (col 0, row 0)
//   Even columns (0, 2, 4): top → bottom
//   Odd  columns (1, 3):    bottom → top
//   Pixel 49: lower-right (col 4, row 9)

function (pixelCount) {
  var map = []
  var cols = 5, rows = 10

  for (var i = 0; i < pixelCount; i++) {
    var col = Math.floor(i / rows)
    var rowInCol = i % rows
    // Even columns descend, odd columns ascend
    var row = (col % 2 === 0) ? rowInCol : (rows - 1 - rowInCol)
    map.push([col, row])
  }

  return map
}
