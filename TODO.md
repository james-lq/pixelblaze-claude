# TODO

## Re-evaluate MCP pattern download (`pixelblaze_get_pattern_code`)

**Context:** During a session to back up all `AAA`/`QN`-prefixed patterns, the MCP tool approach was slow and broken enough that it had to be abandoned in favour of a direct Python script using `pixelblaze-client`.

### Issues observed

1. **Returned JSON-wrapped source instead of raw JS**
   - `pixelblaze_get_pattern_code` returned `{"main": "...source..."}` rather than the JS source string directly.
   - Every downloaded file had to be post-processed to unwrap the JSON envelope before `prettier` could parse it.
   - Root cause is likely in `pixelblaze_tools.py` — the tool probably returns the raw websocket payload without extracting the `main` key.

2. **No bulk / parallel download support**
   - The tool only fetches one pattern at a time, and MCP tool calls cannot be safely parallelised.
   - Downloading 25 patterns one-by-one through the MCP layer was impractically slow.
   - The Python script using `pb.getPatternSourceCode()` in a loop was dramatically faster.

### Suggested fixes

- [ ] In `pixelblaze_tools.py`, unwrap the `{"main": ...}` envelope in `get_pattern_code` before returning — return the raw JS string.
- [ ] Add a bulk download tool (e.g. `pixelblaze_download_patterns`) that accepts a list of IDs or a name filter regex and downloads all matches in one call, saving them to the local patterns directory.
- [ ] Consider whether `getPatternSourceCode` vs `getPatternAsEpe` is the right underlying API call to use.

### Misc

- Evaluate `PBZ` tooling for ideas/alternative strategies:
  https://forum.electromage.com/t/pbz-an-unofficial-cli-js-library-for-pixelblaze-headless-pattern-compiling/4742
