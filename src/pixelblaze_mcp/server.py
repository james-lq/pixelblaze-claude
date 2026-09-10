"""PixelBlaze MCP server entry point.

Run with:
    uv run python -m pixelblaze_mcp.server

Or via the MCP dev inspector:
    uv run mcp dev src/pixelblaze_mcp/server.py
"""

import logging
import sys

from mcp.server.fastmcp import FastMCP

from .config import load_devices, list_projects
from .docs_tools import docs_fetch_page, docs_get_api_reference, docs_get_mapper_reference
from .pixelblaze_tools import (
    pixelblaze_create_pattern,
    pixelblaze_discover_devices,
    pixelblaze_delete_pattern,
    pixelblaze_deploy_local_pattern,
    pixelblaze_get_active_pattern,
    pixelblaze_get_controls,
    pixelblaze_get_device_info,
    pixelblaze_get_pattern_code,
    pixelblaze_get_pixel_map,
    pixelblaze_list_devices,
    pixelblaze_list_local_patterns,
    pixelblaze_list_patterns,
    pixelblaze_regenerate_preview,
    pixelblaze_set_active_pattern,
    pixelblaze_set_brightness,
    pixelblaze_set_control,
    pixelblaze_set_pixel_map,
    pixelblaze_set_offline_mode,
    pixelblaze_update_pattern,
)

# Log to stderr only — stdout is reserved for MCP JSON-RPC messages
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    stream=sys.stderr,
)
logger = logging.getLogger(__name__)

mcp = FastMCP(
    "pixelblaze",
    instructions=(
        "You work with one or more PixelBlaze LED controllers, listed in the "
        "workspace's `devices.toml` registry. Every tool that touches hardware takes "
        "a `device`: its chip ID (`0x` plus 8 upper-case hex digits), its display "
        "name, or a bare IP address for a one-off. Call pixelblaze_list_devices to "
        "see what is registered. A device's address is verified against its chip ID "
        "on every connection, so a tool refuses rather than deploying to the wrong "
        "controller after a DHCP change.\n\n"
        "Patterns are organised into projects under `projects/<name>/patterns/`. "
        "Tools that create or list local files take a `project` (the folder name) or "
        "a `file_path`, which implies its project. A project's `project.toml` sets "
        "its device-name prefix, whether ordinals are auto-assigned, and whether "
        "thumbnails are captured on save.\n\n"
        "PixelBlaze runs LED patterns written in a JavaScript-like language. Each "
        "pattern must define a `render(index)` function that sets pixel colors using "
        "hsv() or rgb(). Patterns can also define `beforeRender(delta)` for per-frame "
        "logic, and export UI controls via special variable naming conventions (e.g. "
        "`export var sliderSpeed` creates a slider). Before writing any pattern code, "
        "call docs_get_api_reference to see all available built-in functions."
    ),
)

# --- PixelBlaze device tools ---

mcp.tool()(pixelblaze_list_devices)
mcp.tool()(pixelblaze_discover_devices)
mcp.tool()(pixelblaze_set_offline_mode)
mcp.tool()(pixelblaze_list_local_patterns)
mcp.tool()(pixelblaze_deploy_local_pattern)
mcp.tool()(pixelblaze_list_patterns)
mcp.tool()(pixelblaze_get_active_pattern)
mcp.tool()(pixelblaze_set_active_pattern)
mcp.tool()(pixelblaze_get_pattern_code)
mcp.tool()(pixelblaze_create_pattern)
mcp.tool()(pixelblaze_update_pattern)
mcp.tool()(pixelblaze_delete_pattern)
mcp.tool()(pixelblaze_get_controls)
mcp.tool()(pixelblaze_set_control)
mcp.tool()(pixelblaze_get_device_info)
mcp.tool()(pixelblaze_set_brightness)
mcp.tool()(pixelblaze_regenerate_preview)
mcp.tool()(pixelblaze_get_pixel_map)
mcp.tool()(pixelblaze_set_pixel_map)

# --- Documentation tools ---

mcp.tool()(docs_get_api_reference)
mcp.tool()(docs_get_mapper_reference)
mcp.tool()(docs_fetch_page)


# --- Resource: quick device context ---

@mcp.resource("pixelblaze://devices")
def device_context() -> str:
    """The registered PixelBlaze devices and the available projects."""
    try:
        registry = load_devices()
    except ValueError as e:
        return f"devices.toml could not be read: {e}"
    lines = ["Registered PixelBlaze devices:"]
    if registry.devices:
        for chip_id, dev in registry.devices.items():
            lines.append(f"  {chip_id}  {dev.name or '(unnamed)'}  at {dev.host}")
    else:
        lines.append("  (none registered — run pixelblaze_discover_devices)")
    lines.append("")
    lines.append(f"Projects: {', '.join(list_projects()) or '(none)'}")
    return "\n".join(lines)


def main():
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
