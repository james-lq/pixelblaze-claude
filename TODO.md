# TODO

## Code sharing between patterns

- Establish a code-sharing workflow so patterns can reuse a common block instead of copy-pasting it between files. The motivating case is the per-channel engine in `projects/H26-Finale`, which every pattern in that project wants and which is currently duplicated by hand. The Pixelblaze language has no imports, so sharing has to happen before the code reaches the device — for example a deploy-time include directive (`// @include lib/channels.js`) resolved by the MCP tooling.
  - Main design constraint: naive expansion breaks the download-and-diff round-trip, because the code on the device would no longer match the file being edited. The expanded region needs delimiters the downloader recognises so an include can be re-collapsed back to the directive on the way in.
  - Decide where shared code lives: per project (`project-*/lib/`), workspace-wide, or both.
  - Consider whether the same mechanism should cover `.mapper.js` files, which have the same "separate file that has to be combined with the pattern" shape.

## Controls and deployment

- Investigate a better way to set **default control values on initial deployment**. A pattern deployed to a device for the first time has no saved control values, so `pixelblaze_get_controls` reads back uninitialised garbage (e.g. `1e34`, `3.7e-40`) and the UI shows nonsense until the values are set by hand. The observed behavior of actual rendering seems inconsistent under this scenario -- it seems like var settings in sources are respected... at least partially. Needs verification.

- Support merging control values a la carte rather than all-or-nothing. `setControls` replaces the whole stored control map instead of merging into it, so writing a single control silently wipes every other value on that pattern back to uninitialised garbage. Observed 2026-09-07 on `02 Frankensparker aftershock`: setting one input reset the other four. The workaround is to read the full map, merge locally, and write it back whole, which every caller currently has to remember to do. A `pixelblaze_set_control` that merges by default would remove the footgun.

- Now that `<stem>.sidecar.toml` carries per-device control values, use them: seed a brand-new control on first deploy from the front entry rather than letting it read uninitialised memory, and add `pixelblaze_restore_controls` for the replacement-device and post-reflash cases. Plan 01 section 6 has the rules; it waits on the merge fix above.

## MCP tooling

- Add a bulk download tool (e.g. `pixelblaze_download_patterns`) accepting a list of IDs or a name filter regex and saving all matches in one call. Downloading 25 patterns one at a time was slow enough that it had to be abandoned in favour of a direct Python script using `pixelblaze-client`, and MCP calls cannot be safely parallelised, so the batching has to happen inside the tool.

- Decide whether `getPatternSourceCode` or `getPatternAsEpe` is the right underlying API call for downloads.

- Make sure the API docs tool loads the latest docs; re-evaluate the local caching.

- Evaluate `PBZ` tooling for ideas and alternative strategies: https://forum.electromage.com/t/pbz-an-unofficial-cli-js-library-for-pixelblaze-headless-pattern-compiling/4742
  - Example: Novel approach of extracting actual device compiler from on-device web service
  - Example: power modeling / prediction tooling?
