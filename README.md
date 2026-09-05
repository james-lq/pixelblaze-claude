# PixelBlaze Claude (LQ Fork)

> Forked from `tomnz`'s repo, as described on [PB forums here](https://forum.electromage.com/t/batteries-included-claude-code-template-project/4667)

Create and iterate on LED patterns for a [PixelBlaze](https://www.bhencke.com/pixelblaze) controller using [Claude Code](https://docs.anthropic.com/en/docs/claude-code). An MCP server connects Claude directly to your PixelBlaze so it can create, update, and manage patterns on the device.

## Adapting for your hardware


1. **Edit the project folder's `CLAUDE.md`** to describe your hardware — pixel layout, how light works physically, what effects look good and which don't
2. **Update the pixel map** on your PixelBlaze to match your physical layout
3. **Ask Claude to help you adapt** — for example:

> "I have a 16x16 LED matrix mounted flat on a wall. Both axes have equal resolution and smooth blending. Update CLAUDE.md to reflect this — we don't need to treat Y as discrete layers, and effects should work as true 2D patterns."

> "I have a cylindrical display with 12 rings of 30 LEDs each. X wraps around the cylinder and Y is the vertical axis. Update CLAUDE.md so patterns account for the X-axis wrapping and create effects that look good on a cylinder."

## What's in the box

- **`src/pixelblaze_mcp/`** -- MCP server that exposes PixelBlaze controls (create/update/delete patterns, set brightness, read device info, etc.)
- **`docs/pixelblaze/`** -- Cached PixelBlaze language reference, available to Claude via the `docs_get_api_reference` tool
- **`CLAUDE.md`** -- Framework instructions that Claude reads automatically (pattern workflow, coding conventions)

## Setup

### Prerequisites

- [PixelBlaze](https://www.bhencke.com/pixelblaze) on your local network
- [Claude Code](https://docs.anthropic.com/en/docs/claude-code) CLI installed
- [uv](https://docs.astral.sh/uv/) (Python package manager)
- Python 3.11+

### 1. Clone and install dependencies

```bash
git clone <repo-url>
cd pixelblaze-ai
uv sync
```

### 2. Configure your PixelBlaze host

Create a `.env` file in the project root (this file is gitignored):

```
PIXELBLAZE_HOST=<your-pixelblaze-ip>
PROJECT_FOLDER=project-layered-acrylic
```

Set `PROJECT_FOLDER` to whichever project folder you are currently working on. The MCP server will use its `patterns/` subfolder automatically.

### 3. Create the MCP config

Create `.mcp.json` in the project root (this file is gitignored). This tells Claude Code how to connect to the MCP server:

```json
{
  "mcpServers": {
    "pixelblaze": {
      "type": "stdio",
      "command": "uv",
      "args": [
        "--directory",
        "/path/to/pixelblaze-ai",
        "run",
        "python",
        "-m",
        "pixelblaze_mcp.server"
      ]
    }
  }
}
```

Replace `/path/to/pixelblaze-ai` with the absolute path to this directory.

### 3. Start Claude Code

```bash
cd pixelblaze-ai
claude
```

Claude will automatically pick up `CLAUDE.md` for project context and `.mcp.json` for the PixelBlaze connection.

## Usage

Once Claude Code is running, you can ask it to create and modify patterns conversationally. Claude has access to the PixelBlaze API reference and can deploy patterns directly to the device.

### Sample prompts

**Creating patterns:**
- "Create a new pattern that looks like rain falling through the layers"
- "Make a bouncing ball effect with configurable speed and size"
- "Create an aurora effect using Perlin noise"

**Modifying patterns:**
- "The heartbeat effect has too much dark time between beats, make it faster"
- "Make the fire pattern symmetric -- both edges should be white-hot"
- "Add more randomization to the comet so it doesn't repeat the same path"

**Adjusting parameters:**
- "Increase the brightness of the fireflies effect"
- "The aurora layers look too similar -- add more color contrast between them"
- "Make the glitch effect more chaotic with panel blackouts and freezes"

**Working with the display:**
- "List all patterns on the device"
- "Switch to the plasma pattern"
- "Set the display brightness to 50%"

### Available MCP tools

Claude has access to these PixelBlaze tools:

| Tool | Description |
|------|-------------|
| `pixelblaze_create_pattern` | Create and activate a new pattern |
| `pixelblaze_update_pattern` | Update an existing pattern's code |
| `pixelblaze_delete_pattern` | Remove a pattern from the device |
| `pixelblaze_list_patterns` | List all patterns on the device |
| `pixelblaze_set_active_pattern` | Switch to a specific pattern |
| `pixelblaze_get_active_pattern` | See which pattern is running |
| `pixelblaze_get_pattern_code` | Read a pattern's source code |
| `pixelblaze_set_brightness` | Set display brightness (0-1) |
| `pixelblaze_get_controls` | Read current slider/control values |
| `pixelblaze_set_control` | Set a slider/control value |
| `pixelblaze_get_device_info` | Get device status and config |
| `docs_get_api_reference` | Get the PixelBlaze language reference |

## Workspace Structure

```
pixelblaze-ai/
  .mcp.json             # MCP server config (gitignored)
  .env                  # PIXELBLAZE_HOST and PATTERNS_DIR (gitignored)
  CLAUDE.md             # Framework instructions for Claude
  pyproject.toml        # Python project config
  src/pixelblaze_mcp/   # MCP server source
  docs/pixelblaze/      # Cached API reference
  project-*/            # Per-project folders (CLAUDE.md + patterns/)
```
