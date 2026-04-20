# 8-Layer Edge-Lit Acrylic Display

The included patterns and design guidance (`CLAUDE.md`) are built for a **2D grid mapped as rows and columns** — specifically an edge-lit acrylic depth display where each row is a separate physical layer. The Y axis represents discrete layers (not a smooth gradient), so patterns are designed to create strong visual contrast and coordinated animation *across* layers while running smooth effects *within* each layer.

This approach works well for any 2D PixelBlaze setup where one axis has significantly fewer pixels than the other (e.g. 8 rows x 32 columns), and where per-row visual differentiation matters more than smooth vertical blending.

**Note:** This project assumes the PixelBlaze's [Mapper](https://electromage.com/docs/mapper) has already been configured correctly for your hardware. The mapper defines the 2D pixel map that tells PixelBlaze which physical LED corresponds to which (x, y) coordinate — patterns depend on this being set up before they can work properly.

The patterns auto-detect the grid dimensions at startup using `mapPixels()`, so they adapt to different sizes without code changes.