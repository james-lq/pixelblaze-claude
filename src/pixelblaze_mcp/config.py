import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env from project root (two levels up from this file)
# TODO JLOM Revisit .env handling, specifically:
# 1. Seems like `dotenv` already handles the find-in-parent logic in a more standard way?
# 2. This implementation apparently does NOT override inherited system environment... is that what we want?
_project_root = Path(__file__).parent.parent.parent
load_dotenv(_project_root / ".env")

PIXELBLAZE_HOST: str = os.environ.get("PIXELBLAZE_HOST", "192.168.2.97")
DOCS_DIR: Path = _project_root / "docs" / "pixelblaze"
PATTERNS_DIR: Path = _project_root / "patterns"

# Persist PB offline mode setting as a file because there's currently no
# proper abstraction for config token management that fits our workflow.
# e.g. storing directly in `.mcp.json` apparently has issues related to MCP server restarts, etc.
_OFFLINE_FLAG: Path = _project_root / ".pixelblaze_offline"


def is_offline() -> bool:
    """Return True if PixelBlaze offline mode is active."""
    if os.environ.get("PIXELBLAZE_OFFLINE", "").lower() in ("1", "true", "yes"):
        return True
    return _OFFLINE_FLAG.exists()


def set_offline(enabled: bool) -> None:
    """Enable or disable offline mode by creating/removing the flag file."""
    if enabled:
        _OFFLINE_FLAG.touch()
    elif _OFFLINE_FLAG.exists():
        _OFFLINE_FLAG.unlink()
