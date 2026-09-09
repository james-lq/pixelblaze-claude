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

from .config import Project

# The header line names the pattern. The sidecar carries the Pattern IDs, one
# per device, so the name is all that stays in the file itself. Keeping it here
# is still worth a line: a pattern downloaded off a device would otherwise lose
# its name on the way to disk.
_HEADER_RE = re.compile(r"^// (.+?)\s*$", re.MULTILINE)

# Recognised only so migration and older files can be read. Nothing writes these.
_LEGACY_SENTINEL = "// ---- pixelblaze-mcp metadata----"
_LEGACY_BLOCK_RE = re.compile(r"\n*" + re.escape(_LEGACY_SENTINEL) + r".*$", re.DOTALL)
_LEGACY_ID_RE = re.compile(r"// .+? — Pattern ID: (\S+)")
_LEGACY_NAME_RE = re.compile(r"// (.+?) — Pattern ID:")
_LEGACY_DEPLOYED_RE = re.compile(r"// @deployed: (.+)")
_LEGACY_HASH_RE = re.compile(r"// @deployed-hash: ([0-9a-f]+)")


def code_hash(code: str) -> str:
    """First 8 hex chars of SHA-256 over the code, trailing whitespace stripped.

    Kept as a thin alias so callers here and in `sidecar` hash identically.
    """
    from .sidecar import content_hash

    return content_hash(strip_legacy_block(code))


def strip_legacy_block(content: str) -> str:
    """Remove a pre-sidecar `// ---- pixelblaze-mcp metadata----` block.

    Nothing writes these any more; this exists so files that still carry one
    read correctly until they are migrated.
    """
    return _LEGACY_BLOCK_RE.sub("", content).rstrip()


def parse_legacy_block(content: str) -> dict[str, str | None]:
    """The `@deployed` / `@deployed-hash` / Pattern ID a pre-sidecar file carries.

    Used by the migration script to build a sidecar from a stamped file.
    """
    id_m = _LEGACY_ID_RE.search(content)
    name_m = _LEGACY_NAME_RE.search(content)
    deployed_m = _LEGACY_DEPLOYED_RE.search(content)
    hash_m = _LEGACY_HASH_RE.search(content)
    return {
        "pattern_id": id_m.group(1) if id_m else None,
        "name": name_m.group(1).strip() if name_m else None,
        "deployed_at": deployed_m.group(1).strip() if deployed_m else None,
        "deployed_hash": hash_m.group(1) if hash_m else None,
    }


def has_legacy_block(content: str) -> bool:
    return _LEGACY_SENTINEL in content or bool(_LEGACY_ID_RE.search(content))


def write_pattern_file(path: Path, code: str, name: str) -> None:
    """Write a pattern's JS file: a name-only header line, then the code.

    No metadata is stored in the file. Where the pattern has been deployed, and
    with what control values, lives in its `.sidecar.toml`.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(ensure_header(code, name).rstrip() + "\n", encoding="utf-8")


def parse_pattern_file(path: Path) -> dict[str, Any]:
    """Parse a pattern JS file: its name, its code, and its deployment history.

    Deployment facts come from the sidecar, so `modified_since_deployed` is
    computed by comparing the current code's hash with what the front entry
    recorded. It is None when the pattern has never been deployed.
    """
    from . import sidecar as sidecar_mod

    content = path.read_text(encoding="utf-8")
    code = strip_legacy_block(content)
    legacy = parse_legacy_block(content)

    # A migrated file has a name-only header; a legacy one has `Name — Pattern ID: x`.
    name = legacy["name"]
    if not name:
        header = _HEADER_RE.search(content)
        name = header.group(1).strip() if header else path.stem

    sc = sidecar_mod.load(path)
    front = sc.front
    return {
        "name": name,
        "path": path,
        "code": code,
        "sidecar": sc,
        "pattern_id": front.pattern_id if front else legacy["pattern_id"],
        "device_id": front.device_id if front else None,
        "device_name": front.device_name if front else None,
        "deployed_at": front.deployed_at.isoformat().replace("+00:00", "Z") if front
        else legacy["deployed_at"],
        "modified_since_deployed": sc.modified_since_deployed(code),
        "legacy_metadata": has_legacy_block(content),
    }


def find_local_pattern_file(pattern_id: str) -> Path | None:
    """The pattern file whose sidecar records this ID, across every project."""
    from . import sidecar as sidecar_mod

    hit = sidecar_mod.find_by_pattern_id(pattern_id)
    return hit[0] if hit else None


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


def ensure_header(code: str, name: str) -> str:
    """Make sure the file's first line is the name-only header `// <Name>`.

    The check is against the expected name, not merely "starts with //". Plenty
    of patterns open with a comment block of their own, and treating any leading
    comment as the header silently loses the name — which is the one thing the
    header exists to carry, now that Pattern IDs live in the sidecar.

    A legacy `// <Name> — Pattern ID: <id>` line counts as the header until the
    file is migrated, so this stays idempotent either way.
    """
    stripped = code.lstrip()
    first = stripped.splitlines()[0].strip() if stripped else ""
    if first == f"// {name}":
        return code
    legacy = _LEGACY_NAME_RE.match(first)
    if legacy and legacy.group(1).strip() == name:
        return code
    return f"// {name}\n{stripped}"
