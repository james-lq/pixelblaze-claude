"""Utilities for reading/writing PixelBlaze pattern JS files with embedded mcp metadata."""

import hashlib
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .config import PATTERNS_DIR

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
    h = code_hash(code)
    body = strip_mcp_block(code)

    # Replace (pending) placeholder in the first comment line with the real ID
    if deployed_at is not None:
        body = re.sub(
            r"(// .+? — Pattern ID: )\(pending\)",
            rf"\g<1>{pattern_id}",
            body,
            count=1,
        )

    mcp_block = (
        f"\n\n{_MCP_SENTINEL}\n"
        f"// @deployed: {ts}\n"
        f"// @deployed-hash: {h}\n"
        f"// @modified-since-deployed: false\n"
    )

    PATTERNS_DIR.mkdir(exist_ok=True)
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
    """Scan the patterns directory (PATTERNS_DIR) for a JS file containing the given Pattern ID."""
    if not PATTERNS_DIR.exists():
        return None
    for path in PATTERNS_DIR.glob("*.js"):
        try:
            if f"Pattern ID: {pattern_id}" in path.read_text(encoding="utf-8"):
                return path
        except OSError:
            continue
    return None


def _slugify(name: str) -> str:
    slug = name.lower()
    slug = re.sub(r"[^\w\s-]", "", slug)
    slug = re.sub(r"[\s_]+", "-", slug)
    slug = re.sub(r"-+", "-", slug)
    return slug.strip("-")


def _next_ordinal() -> int:
    if not PATTERNS_DIR.exists():
        return 1
    max_ord = 0
    for f in PATTERNS_DIR.glob("*.js"):
        m = re.match(r"^(\d+)-", f.name)
        if m:
            max_ord = max(max_ord, int(m.group(1)))
    return max_ord + 1


def new_pattern_file_path(name: str) -> Path:
    """Generate the next available file path in PATTERNS_DIR for the given pattern name."""
    return PATTERNS_DIR / f"{_next_ordinal():02d}-{_slugify(name)}.js"
