// Pattern: AAA Easy Mapper 2
// ID: JTWwprXjTepygGZJh

pixels = array(pixelCount);

export var currentPixel;
currentPixel = 0;

// Mode
// 0: Single-pixel
// 1: All-pixel
// 2: Cycle pixels
export var mode;
mode = 0;

//export var activePixels;

export function inputNumberPixel(v) {
  currentPixel = v;
}

export function inputNumberMode(v) {
  mode = v;
}

// TODO BIZARRELY, this simple iteration causes "Execution steps exhausted"
// function includes(array, value)
// {
//     for (i = 0; i < array.length; i++)
//     {
//         if (array[i] == value)
//             return true;
//     }

//     return false;
// }

export function beforeRender(delta) {
  currentDelta = delta;

  if (mode == 0) {
    pixels.mutate((v, i, a) => (i == currentPixel ? 1 : 0));
  } else if (mode == 1) {
    pixels.mutate((v, i, a) => (i <= currentPixel ? 1 : 0));
  } else if (mode == 2) {
    pixels.mutate((v, i, a) => 0);
  }

  //   activePixels = [currentPixel, 50, 74];

  //   for (i = 0; i < pixelCount; i++)
  //   {
  //     if(includes(activePixels, i))
  //     {
  //         pixels[i] = 1;
  //     }
  //     else
  //     {
  //         pixels[i] = 0;
  //     }
  //   }
}

export function render(index) {
  v = pixels[index];
  rgb(v, v, v);
}
