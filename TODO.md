# TODO

## Workflow

- Revisit root .env file changes requiring an MCP restart, particularly device address.

- Configure device per project

- Stretch: Define named devices and make deploying projects to different devices easier.

- Make sure API docs load the latest docs? Do I need to re-evaluate local caching?

## Pattern Naming and Metadata

- Allow projects to define a pattern name prefix, e.g. `H26 - `

- Move the auto-generated metadata block to a sidecar file (see `CLAUDE.md` TODO) rather than patching the in-file parser further. Needs a migration for already-stamped files in the existing projects; do as its own commit.

- Investigate a better way to set **default control values on initial deployment**. A pattern deployed to a device for the first time has no saved control values, so `pixelblaze_get_controls` reads back uninitialised garbage (e.g. `1e34`, `3.7e-40`) and the UI shows nonsense until the values are set by hand. The observed behavior of actual rendering seems inconsistent under this scenario -- it seems like var settings in sources are respected... at least partially. Needs verification.

## Re-evaluate MCP pattern download (`pixelblaze_get_pattern_code`)

**Context:** During a session to back up all `AAA`/`QN`-prefixed patterns, the MCP tool approach was slow enough that it had to be abandoned in favour of a direct Python script using `pixelblaze-client`.

### Issues observed

- **No bulk / parallel download support.** The tool only fetches one pattern at a time, and MCP tool calls cannot be safely parallelised. Downloading 25 patterns one-by-one through the MCP layer was impractically slow; a Python script calling `pb.getPatternSourceCode()` in a loop was dramatically faster.

### Suggested fixes

- Add a bulk download tool (e.g. `pixelblaze_download_patterns`) that accepts a list of IDs or a name filter regex and downloads all matches in one call, saving them to the local patterns directory.
- Consider whether `getPatternSourceCode` vs `getPatternAsEpe` is the right underlying API call to use.

### Misc

- Evaluate `PBZ` tooling for ideas/alternative strategies:
  https://forum.electromage.com/t/pbz-an-unofficial-cli-js-library-for-pixelblaze-headless-pattern-compiling/4742
