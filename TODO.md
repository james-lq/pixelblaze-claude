# TODO

## Device configuration

- The device address lives in the root `.env` and is read once when the MCP server starts, so pointing the tooling at a different device requires restarting the server. Make the device configurable per project instead.

- Stretch: define named devices, so deploying a project to a particular device is a first-class operation rather than an `.env` edit.

## Pattern naming and metadata

- Allow projects to define a pattern name prefix, e.g. `H26 - `

- Move the auto-generated metadata block to a sidecar file (see `CLAUDE.md` TODO) rather than patching the in-file parser further. Needs a migration for already-stamped files in the existing projects; do as its own commit.

## Controls and deployment

- Investigate a better way to set **default control values on initial deployment**. A pattern deployed to a device for the first time has no saved control values, so `pixelblaze_get_controls` reads back uninitialised garbage (e.g. `1e34`, `3.7e-40`) and the UI shows nonsense until the values are set by hand. The observed behavior of actual rendering seems inconsistent under this scenario -- it seems like var settings in sources are respected... at least partially. Needs verification.

- Support merging control values a la carte rather than all-or-nothing. `setControls` replaces the whole stored control map instead of merging into it, so writing a single control silently wipes every other value on that pattern back to uninitialised garbage. Observed 2026-09-07 on `02 Frankensparker aftershock`: setting one input reset the other four. The workaround is to read the full map, merge locally, and write it back whole, which every caller currently has to remember to do. A `pixelblaze_set_control` that merges by default would remove the footgun.

- Consider a per-pattern sidecar file holding control values, both declared defaults and the last-known "current" values pulled off the device. Would give several things at once: values under version control instead of living only in device flash, a way to seed a brand-new control on first deploy rather than letting it read uninitialised memory (see the default control values item above), restore onto a replacement device or after a reflash, and a diffable record of tuning. Probably shares a mechanism with the metadata sidecar item above, so consider designing the two together.

## MCP tooling

- Add a bulk download tool (e.g. `pixelblaze_download_patterns`) accepting a list of IDs or a name filter regex and saving all matches in one call. Downloading 25 patterns one at a time was slow enough that it had to be abandoned in favour of a direct Python script using `pixelblaze-client`, and MCP calls cannot be safely parallelised, so the batching has to happen inside the tool.

- Decide whether `getPatternSourceCode` or `getPatternAsEpe` is the right underlying API call for downloads.

- Make sure the API docs tool loads the latest docs; re-evaluate the local caching.

- Evaluate `PBZ` tooling for ideas and alternative strategies: https://forum.electromage.com/t/pbz-an-unofficial-cli-js-library-for-pixelblaze-headless-pattern-compiling/4742
  - Example: Novel approach of extracting actual device compiler from on-device web service
  - Example: power modeling / prediction tooling?
