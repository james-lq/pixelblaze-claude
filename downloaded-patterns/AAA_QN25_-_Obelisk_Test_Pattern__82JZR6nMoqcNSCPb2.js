// Pattern: AAA QN25 - Obelisk Test Pattern
// ID: 82JZR6nMoqcNSCPb2

/*
  Knight Rider: A car named KITT gains sentience and fights critme and all that 
  good stuff.
  
  Want to learn how to code patterns like this? This pattern has a YouTube
  video walkthrough:
  
    https://www.youtube.com/watch?v=3ugNIZ96UK4
*/

leader = 0;
direction = 1;
pixels = array(pixelCount);
pixelsCat = array(370);
pixelsShroom1 = array(50);
pixelsShroom2 = array(50);

function fillPixelSet(start, count, hue, calcValue) {
  for (i = start; i < count; i++) {
    pixels[i] -= calcValue;
    pixels[i] = max(0, pixels[i]);
  }
}

speed = pixelCount / 4000;
fade = 0.0007;
export function beforeRender(delta) {
  lastLeader = floor(leader);
  leader += direction * delta * speed;

  if (leader >= pixelCount) {
    direction = -direction;
    leader = pixelCount - 1;
  }

  if (leader < 0) {
    direction = -direction;
    leader = 0;
  }

  // Fill pixels between frames. Added after the video walkthrough was uploaded.
  up = lastLeader < leader;
  for (i = lastLeader; i != floor(leader); up ? i++ : i--) pixels[i] = 1;

  // TODO JLOM Whoops, insufficient hack -- doesn't handle the leader calculation
  calcValue = delta * fade;

  fillPixelSet(0, pixelCount, calcValue);
  //fillPixelSet(37, 50, calcValue)
  //fillPixelSet(87, 50, calcValue)
}

export function render(index) {
  if (index < 185) hue = 0.7;
  else if (index < 370) hue = 0.1;
  else hue = 0.5;

  hsv(hue, 1, 0.5);

  //v = pixels[index]
  //v = v * v * v
  //hsv(0.7, 1, v)
}
