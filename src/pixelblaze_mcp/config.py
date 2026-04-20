import os
from pathlib import Path
from dotenv import load_dotenv

_project_root = Path(__file__).parent.parent.parent
# Searches up from this file's directory; does not override inherited env vars.
load_dotenv()

_host = os.environ.get("PIXELBLAZE_HOST")
if not _host:
    raise EnvironmentError(
        "PIXELBLAZE_HOST is not set. Create a .env file in the project root:\n"
        "  PIXELBLAZE_HOST=<your-pixelblaze-ip>"
    )
PIXELBLAZE_HOST: str = _host
DOCS_DIR: Path = _project_root / "docs" / "pixelblaze"

# TODO Revisit mixed-metaphor usage of "project" concept vs "workspace" 
# ...or some other way to organize the tool code vs. specific user projects.
# Set PROJECT_FOLDER in .env to the active project's folder.
# Relative paths are resolved from the workspace root.
# Example: PROJECT_FOLDER=project-layered-acrylic
_project_folder_env = os.environ.get("PROJECT_FOLDER")
if _project_folder_env:
    _project_folder_path = Path(_project_folder_env)
    PROJECT_FOLDER: Path = _project_folder_path if _project_folder_path.is_absolute() else _project_root / _project_folder_path
else:
    PROJECT_FOLDER: Path = _project_root
PATTERNS_DIR: Path = PROJECT_FOLDER / "patterns"

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
