// Pattern: AAA QN24 Easy Mapper
// ID: 6QT84xpNAY4YqyQHM

pixels = array(pixelCount);

export var currentPixel;
currentPixel = 0;

export var currentDelta;

export function inputNumberPixel(v) {
  currentPixel = v;
}

export function beforeRender(delta) {
  currentDelta = delta;

  for (i = 0; i < pixelCount; i++) {
    //pixels[i] = 0.5;
    pixels[i] = i == currentPixel ? 1 : 0;
  }
}

export function render(index) {
  v = pixels[index];
  rgb(v, v, v);
}
