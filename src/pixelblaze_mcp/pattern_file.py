"""Utilities for reading/writing PixelBlaze pattern JS files with embedded mcp metadata.

Naming, in both directions:

    local file:    projects/H26-Finale/patterns/03 Spark Chorus.js
    device name:   H26-Finale 03 Spark Chorus
                   ^^^^^^^^^^ project prefix     ^^ optional ordinal

The filename stem never carries the prefix — the project folder already groups
files locally — so the invariant is `device name == "<prefix> <stem>"`, a pure
function in both directions.
"""

import hashlib
import re
from pathlib import Path
from typing import Any

from .config import PROJECTS_DIR, Project

_MCP_SENTINEL = "// ---- pixelblaze-mcp metadata----"

# Matches the sentinel line through end of file (greedy) — used to strip the block
_MCP_BLOCK_RE = re.compile(r"\n*" + re.escape(_MCP_SENTINEL) + r".*$", re.DOTALL)

_PATTERN_ID_RE = re.compile(r"// .+? — Pattern ID: (\S+)")
_DEPLOYED_RE = re.compile(r"// @deployed: (.+)")
_HASH_RE = re.compile(r"// @deployed-hash: ([0-9a-f]+)")
_NAME_RE = re.compile(r"// (.+?) — Pattern ID:")


def code_hash(code: str) -> str:
    """First 8 hex chars of SHA-256 of code content, excluding any mcp block."""
    stripped = _MCP_BLOCK_RE.sub("", code).rstrip()
    return hashlib.sha256(stripped.encode()).hexdigest()[:8]


def strip_mcp_block(content: str) -> str:
    """Remove the mcp metadata block (and preceding blank line) from file content."""
    return _MCP_BLOCK_RE.sub("", content).rstrip()


def _parse_mcp_block(content: str) -> dict[str, str | None]:
    """Extract deployed_at and stored_hash from the mcp metadata block, if present."""
    m = re.search(re.escape(_MCP_SENTINEL) + r"(.+?)$", content, re.DOTALL)
    if not m:
        return {"deployed_at": None, "stored_hash": None}
    block = m.group(0)
    deployed_m = _DEPLOYED_RE.search(block)
    hash_m = _HASH_RE.search(block)
    return {
        "deployed_at": deployed_m.group(1).strip() if deployed_m else None,
        "stored_hash": hash_m.group(1) if hash_m else None,
    }


def stamp_file(path: Path, code: str, pattern_id: str, deployed_at: str | None) -> None:
    """Write a pattern JS file stamped with mcp metadata at the end.

    deployed_at=None marks the pattern as pending (never deployed to device).
    Also updates any '(pending)' Pattern ID placeholder in the first comment line
    when a real pattern_id is provided.
    """
    ts = deployed_at or "(pending)"
    body = strip_mcp_block(code)

    # Replace (pending) placeholder in the first comment line with the real ID
    if deployed_at is not None:
        body = re.sub(
            r"(// .+? — Pattern ID: )\(pending\)",
            rf"\g<1>{pattern_id}",
            body,
            count=1,
        )

    # Hash the body as it will be written (after the ID substitution), so a
    # freshly stamped file does not immediately read as modified.
    h = code_hash(body)

    mcp_block = (
        f"\n\n{_MCP_SENTINEL}\n"
        f"// @deployed: {ts}\n"
        f"// @deployed-hash: {h}\n"
        f"// @modified-since-deployed: false\n"
    )

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body + mcp_block, encoding="utf-8")


def update_local_code(path: Path, new_code: str) -> None:
    """Save new code to an existing local file, preserving the mcp metadata block.

    The stored hash is intentionally NOT updated — leaving a mismatch so that
    list_local_patterns and parse_pattern_file report modified_since_deployed=True.
    The @modified-since-deployed line in the file is also set to true explicitly.
    """
    content = path.read_text(encoding="utf-8")
    mcp = _parse_mcp_block(content)
    body = strip_mcp_block(new_code)

    if mcp["deployed_at"] is not None:
        # Re-write with unchanged deployed_at/hash so the drift is detectable
        mcp_block = (
            f"\n\n{_MCP_SENTINEL}\n"
            f"// @deployed: {mcp['deployed_at']}\n"
            f"// @deployed-hash: {mcp['stored_hash']}\n"
            f"// @modified-since-deployed: true\n"
        )
        path.write_text(body + mcp_block, encoding="utf-8")
    else:
        # No mcp block yet — just write the code; will be stamped on first deploy
        path.write_text(body, encoding="utf-8")


def parse_pattern_file(path: Path) -> dict[str, Any]:
    """Parse a pattern JS file and return metadata including live modified status."""
    content = path.read_text(encoding="utf-8")
    mcp = _parse_mcp_block(content)
    code = strip_mcp_block(content)

    name_m = _NAME_RE.search(content)
    id_m = _PATTERN_ID_RE.search(content)
    name = name_m.group(1) if name_m else path.stem
    pattern_id = id_m.group(1) if id_m else None

    stored_hash = mcp["stored_hash"]
    deployed_at = mcp["deployed_at"]

    # Dynamically compute modified status by re-hashing current code vs stored hash
    if stored_hash is None or deployed_at is None:
        modified: bool | None = None  # no metadata — unknown
    elif deployed_at == "(pending)":
        modified = False  # never deployed; not "modified since deploy"
    else:
        modified = code_hash(code) != stored_hash

    return {
        "name": name,
        "pattern_id": pattern_id,
        "deployed_at": deployed_at,
        "stored_hash": stored_hash,
        "modified_since_deployed": modified,
        "path": path,
        "code": code,
    }



def find_local_pattern_file(pattern_id: str) -> Path | None:
    """Find the JS file carrying a given Pattern ID, across every project.

    Phase 1 of plan 01 keeps the ID in the file's header line, so this greps
    `projects/*/patterns/*.js`. It is cheap (a few dozen small files) and
    unambiguous: IDs are 17 random characters minted per device, so collisions
    do not happen in practice. Phase 2 replaces this with the same scan over
    `*.sidecar.toml`, which is the same shape with the ID in a different file.
    """
    if not PROJECTS_DIR.exists():
        return None
    needle = f"Pattern ID: {pattern_id}"
    for path in sorted(PROJECTS_DIR.glob("*/patterns/*.js")):
        try:
            if needle in path.read_text(encoding="utf-8"):
                return path
        except OSError:
            continue
    return None


# Characters that are illegal in filenames on Windows (superset of macOS/Linux).
_ILLEGAL_FILENAME_CHARS = re.compile(r'[<>:"/\\|?*\x00-\x1f]')
_ORDINAL_PREFIX_RE = re.compile(r"^(\d+)[- ]")


def _safe_filename(name: str) -> str:
    return _ILLEGAL_FILENAME_CHARS.sub("-", name).strip().rstrip(".")


def _next_ordinal(project: Project) -> int:
    """Next 2-digit ordinal for a project, counting both `NN Name.js` and
    legacy `NN-name.js` files."""
    patterns_dir = project.patterns_dir
    if not patterns_dir.exists():
        return 1
    max_ord = 0
    for f in patterns_dir.glob("*.js"):
        m = _ORDINAL_PREFIX_RE.match(f.name)
        if m:
            max_ord = max(max_ord, int(m.group(1)))
    return max_ord + 1


def canonical_pattern_name(name: str, project: Project) -> str:
    """The filename stem for a pattern: filename-safe, and prefixed with the
    next free ordinal when the project asks for ordinals and the name lacks one.

    This is the *local* name. It never carries the project's device-name prefix;
    `device_pattern_name()` adds that on the way to the device.
    """
    base = _safe_filename(name)
    if project.ordinals == "auto" and not _ORDINAL_PREFIX_RE.match(base):
        base = f"{_next_ordinal(project):02d} {base}"
    return base


def device_pattern_name(stem: str, project: Project) -> str:
    """The display name a pattern takes on the device: `<prefix> <stem>`.

    An empty `pattern_name_prefix` means the pattern deploys under its bare
    filename stem.
    """
    prefix = project.pattern_name_prefix
    return f"{prefix} {stem}" if prefix else stem


def stem_from_device_name(device_name: str, project: Project) -> str | None:
    """The filename stem a device pattern name maps back to, or None if the
    name does not belong to this project.

    A pattern whose name does not carry the project's prefix is not ours —
    the right answer for hand-made or downloaded patterns sharing the device.
    """
    prefix = project.pattern_name_prefix
    if not prefix:
        return device_name
    if device_name.startswith(prefix + " "):
        return device_name[len(prefix) + 1:]
    return None


def new_pattern_file_path(stem: str, project: Project) -> Path:
    """Where a new pattern's JS file goes: `<project>/patterns/<stem>.js`."""
    return project.patterns_dir / f"{stem}.js"


def ensure_header(code: str, name: str, pattern_id: str = "(pending)") -> str:
    """Prepend the `// <Name> — Pattern ID: <id>` header line if the code lacks one.

    `name` is the local filename stem, not the device display name: the header
    identifies the local file, and phase 1 of plan 01 still locates a pattern's
    file by grepping this line for its ID.
    """
    if _PATTERN_ID_RE.search(code):
        return code
    return f"// {name} — Pattern ID: {pattern_id}\n{code.lstrip()}"
