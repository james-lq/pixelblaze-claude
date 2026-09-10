# TODO

## Code sharing between patterns

- Establish a code-sharing workflow so patterns can reuse a common block instead of copy-pasting it between files. The motivating case is the per-channel engine in `projects/H26-Finale`, which every pattern in that project wants and which is currently duplicated by hand. The Pixelblaze language has no imports, so sharing has to happen before the code reaches the device — for example a deploy-time include directive (`// @include lib/channels.js`) resolved by the MCP tooling.
  - Main design constraint: naive expansion breaks the download-and-diff round-trip, because the code on the device would no longer match the file being edited. The expanded region needs delimiters the downloader recognises so an include can be re-collapsed back to the directive on the way in.
  - Decide where shared code lives: per project (`project-*/lib/`), workspace-wide, or both.
  - Consider whether the same mechanism should cover `.mapper.js` files, which have the same "separate file that has to be combined with the pattern" shape.

## MCP tooling

- Consider an in-memory `pixelblaze_use(project=..., device=...)` setting process-lifetime defaults, if passing `device=` per call turns out to be noisy in practice. Deferred deliberately when the multi-device work landed: being memory-only it cannot recreate the restart problem that work removed, but it should not be added until the per-call form has been lived with.

- Add a bulk download tool (e.g. `pixelblaze_download_patterns`) accepting a list of IDs or a name filter regex and saving all matches in one call. Downloading 25 patterns one at a time was slow enough that it had to be abandoned in favour of a direct Python script using `pixelblaze-client`, and MCP calls cannot be safely parallelised, so the batching has to happen inside the tool.

- Decide whether `getPatternSourceCode` or `getPatternAsEpe` is the right underlying API call for downloads.

- Make sure the API docs tool loads the latest docs; re-evaluate the local caching.

- Evaluate `PBZ` tooling for ideas and alternative strategies: https://forum.electromage.com/t/pbz-an-unofficial-cli-js-library-for-pixelblaze-headless-pattern-compiling/4742
  - Example: Novel approach of extracting actual device compiler from on-device web service
  - Example: power modeling / prediction tooling?
