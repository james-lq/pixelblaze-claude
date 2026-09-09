## Planned installation

### LED Hardaware
- Pixelblaze v3 + Sensor Board + Output Expander
- WS2811 LEDs, 2 strings 50 LEDs each.
- Each string connected to a channel on the output expander.

### Geometry / Pattern Design

- Strings hanging vertically in a grid arrangement. Each column of the grid is 12 pixels high. Each string starts at the lower-left, and zig-zags back down and up to fill out 4 columns (i.e. 48 pixels form 4 columns of 12, with 2 ununsed pixels at the end). Two strings means 8 columns by 12 rows.

- Pixels have 7" of space between them, in both vertical cols and horizontal rows.

- Multiple "visual channels", corresponding to frequency bins in the spectral analysis.

- Flexible relationship between logical visual channels and actual LED strings
  - e.g. I want option to map visual channels to one or more column of the grid.

## PB Docs / Reference

### Sensor board reference page:
https://electromage.com/docs/sensor-expansion-board#sound

### Example pattern that does auto-gain correction
`sound - spectromatrix optim`

## Feature Creep

1. If we are connected to internet, can auto-schedule activation?