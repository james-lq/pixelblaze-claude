## PB Docs / Reference

### Example "Shake to switch modes" from SensorBoard 1.0 doc

```
// Shake to switch modes

export var accelerometer  // Enable the accelerometer
mode = debounce = 0

export function beforeRender(delta) {
  // 3D vector sum of x, y, and z acceleration
  totalAcceleration = sqrt(
    accelerometer[0] * accelerometer[0] +
    accelerometer[1] * accelerometer[1] +
    accelerometer[2] * accelerometer[2]
  )

  debounce = clamp(debounce + delta, 0, 2000) // Prevent overflow

  // Cycle mode if sensor board is shaken, no more than 1x / sec
  if (debounce > 1000 && totalAcceleration > 0.03) {
    mode = (mode + 1) % 3
    debounce = 0
  }
}

h = s = v = 1
modes = array(3)
modes[0] = (index) => { h = 1 - index / pixelCount / 4; v = 1 }
modes[1] = (index) => { h = 0.5; v = index % 2 }
modes[2] = (index) => { h = wave((index+wave(time(0.04))*5)/pixelCount)*6; v = 0.1+random(wave(time(0.03))) }

export function render(index) {
  modes[mode](index)
  hsv(h, s, v)
}
```
