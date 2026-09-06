# TODO

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

## Pattern file metadata

- Move the auto-generated metadata block to a sidecar file (see `CLAUDE.md` TODO) rather than patching the in-file parser further. Needs a migration for already-stamped files in the existing projects; do as its own commit.
