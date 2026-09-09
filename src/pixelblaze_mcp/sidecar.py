"""Per-pattern sidecar files: where a pattern has been deployed, and with what.

`patterns/<stem>.sidecar.toml` sits beside `patterns/<stem>.js` and records one
entry per device the pattern has ever been deployed to, most recent first. The
front entry is the pattern's current device, which is what "redeploy with no
`device` argument" means.

This replaces the in-file `// ---- pixelblaze-mcp metadata----` block. A pattern
ID is minted per device, so the old header line could only ever hold one, which
is why it could not describe a pattern living on two controllers.

Renaming a pattern means renaming its sidecar (and any `.mapper.js`) with it:
the three are matched by stem, and nothing goes looking for orphans. A `.js`
with no sidecar is simply "never deployed".
"""

import hashlib
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import tomlkit
from pydantic import BaseModel, ConfigDict, ValidationError

from . import config
from .config import format_chip_id

SIDECAR_SUFFIX = ".sidecar.toml"

HEADER_COMMENT = (
    "Written by the pixelblaze-mcp tooling on every deploy. Most recent device first.\n"
    "Renaming the pattern means renaming this file with it."
)

# A control value as the device stores it: sliders are floats, toggles are
# booleans, and colour pickers are arrays of three floats. These round-trip as
# their own TOML types; the tooling must never coerce one into another.
ControlValue = float | int | bool | list[float]


def content_hash(text: str) -> str:
    """First 8 hex chars of SHA-256 over the text, trailing whitespace stripped.

    Used for both `deployed_hash` (the code as sent to the device) and
    `map_hash` (the pixel map source).
    """
    return hashlib.sha256(text.rstrip().encode()).hexdigest()[:8]


class DeploymentEntry(BaseModel):
    """One device's record: what went there, when, and what the controls were."""

    model_config = ConfigDict(extra="forbid")

    device_id: str
    pattern_id: str
    deployed_at: datetime
    deployed_hash: str
    # A hint for humans, expected to drift; never used for matching.
    device_name: str | None = None
    # Absent when no pixel map was involved in the deploy.
    map_hash: str | None = None
    controls: dict[str, Any] = {}


def sidecar_path(js_path: Path) -> Path:
    """The sidecar beside a pattern file: `<stem>.sidecar.toml`."""
    return js_path.with_suffix("") .with_name(js_path.stem + SIDECAR_SUFFIX)


class Sidecar:
    """A pattern's deployment history, backed by a `tomlkit` document.

    Tooling owns every key in this file, so a rewrite is free to reorder the
    history. Comments *inside* a history entry will not survive a reordering;
    the top-of-file comment does, and is written on creation.
    """

    def __init__(self, path: Path, doc: tomlkit.TOMLDocument, entries: list[DeploymentEntry]):
        self.path = path
        self.doc = doc
        self.entries = entries

    # --- Reading ----------------------------------------------------------

    @property
    def front(self) -> DeploymentEntry | None:
        """The pattern's current device: the most recent deployment."""
        return self.entries[0] if self.entries else None

    def entry_for(self, device_id: str) -> DeploymentEntry | None:
        device_id = format_chip_id(device_id)
        return next((e for e in self.entries if e.device_id == device_id), None)

    def modified_since_deployed(self, code: str) -> bool | None:
        """Whether the local code has drifted from what the front entry recorded.

        None when there is no history to compare against. This is computed, never
        stored — the old metadata block's `@modified-since-deployed` line was
        redundant with the hash sitting next to it.
        """
        if self.front is None:
            return None
        return content_hash(code) != self.front.deployed_hash

    # --- Writing ----------------------------------------------------------

    def record(
        self,
        *,
        device_id: str,
        pattern_id: str,
        deployed_hash: str,
        device_name: str | None = None,
        deployed_at: datetime | None = None,
        controls: dict[str, Any] | None = None,
        map_hash: str | None = None,
    ) -> DeploymentEntry:
        """Record a deploy, updating this device's entry in place and moving it
        to the front. Does not write the file; call `save()`."""
        device_id = format_chip_id(device_id)
        existing = self.entry_for(device_id)
        entry = DeploymentEntry(
            device_id=device_id,
            pattern_id=pattern_id,
            deployed_at=deployed_at or datetime.now(timezone.utc).replace(microsecond=0),
            deployed_hash=deployed_hash,
            device_name=device_name if device_name is not None else (
                existing.device_name if existing else None
            ),
            map_hash=map_hash if map_hash is not None else (existing.map_hash if existing else None),
            # Controls are refreshed by the caller reading them back off the
            # device; absent means "leave what was recorded before".
            controls=controls if controls is not None else (existing.controls if existing else {}),
        )
        if existing is not None:
            self.entries.remove(existing)
        self.entries.insert(0, entry)
        return entry

    def remove(self, device_id: str) -> bool:
        """Drop one device's entry. Returns whether there was one."""
        entry = self.entry_for(device_id)
        if entry is None:
            return False
        self.entries.remove(entry)
        return True

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(tomlkit.dumps(self._rebuild()), encoding="utf-8")

    def _rebuild(self) -> tomlkit.TOMLDocument:
        """Replace the history in the document, leaving anything else alone."""
        doc = self.doc
        aot = tomlkit.aot()
        for entry in self.entries:
            aot.append(_entry_to_table(entry))
        doc["deployment_history"] = aot
        return doc


def _entry_to_table(entry: DeploymentEntry) -> tomlkit.items.Table:
    table = tomlkit.table()
    table["device_id"] = entry.device_id
    if entry.device_name is not None:
        table["device_name"] = entry.device_name
        table.value.item("device_name").comment(
            "display name at deploy time; a hint, not used for matching"
        )
    table["pattern_id"] = entry.pattern_id
    table["deployed_at"] = entry.deployed_at
    table["deployed_hash"] = entry.deployed_hash
    if entry.map_hash is not None:
        table["map_hash"] = entry.map_hash
        table.value.item("map_hash").comment("pixel map on the device at deploy time")
    # A sub-table of an array-of-tables element attaches to that element, so this
    # renders as [deployment_history.controls] under the entry it belongs to.
    controls = tomlkit.table()
    for name, value in entry.controls.items():
        controls[name] = value
    table["controls"] = controls
    return table


def new_document() -> tomlkit.TOMLDocument:
    """A fresh sidecar document carrying the explanatory header comment."""
    doc = tomlkit.document()
    for line in HEADER_COMMENT.splitlines():
        doc.add(tomlkit.comment(line))
    doc.add(tomlkit.nl())
    return doc


def load(js_path: Path) -> Sidecar:
    """The sidecar for a pattern file, or an empty one if it has none yet."""
    path = sidecar_path(js_path)
    if not path.exists():
        return Sidecar(path, new_document(), [])
    try:
        doc = tomlkit.parse(path.read_text(encoding="utf-8"))
    except Exception as e:
        raise ValueError(f"Could not parse {path}: {e}") from e

    raw = doc.unwrap().get("deployment_history", [])
    if not isinstance(raw, list):
        raise ValueError(f"{path.name}: deployment_history must be a list of [[tables]]")
    entries: list[DeploymentEntry] = []
    for i, item in enumerate(raw):
        try:
            entry = DeploymentEntry(**item)
            entry.device_id = format_chip_id(entry.device_id)
        except (ValidationError, ValueError) as e:
            raise ValueError(f"{path.name}: deployment_history entry {i + 1} is not valid.\n{e}") from e
        entries.append(entry)
    # "Most recent device first" is the file's stated invariant. Sorting on load
    # keeps it true even if the file has been hand-edited, and makes `front`
    # agree with `most_recent_device()`, which compares timestamps.
    entries.sort(key=lambda e: e.deployed_at, reverse=True)
    return Sidecar(path, doc, entries)


def exists_for(js_path: Path) -> bool:
    return sidecar_path(js_path).exists()


def find_by_pattern_id(pattern_id: str) -> tuple[Path, DeploymentEntry] | None:
    """Locate the pattern file whose sidecar records this ID, and that entry.

    Scans every project. Pattern IDs are 17 random characters minted per device,
    so a match is unambiguous in practice. This is what lets `update_pattern`
    take an ID alone and work out both the project and the device.
    """
    if not config.PROJECTS_DIR.exists():
        return None
    for path in sorted(config.PROJECTS_DIR.glob(f"*/patterns/*{SIDECAR_SUFFIX}")):
        js_path = path.with_name(path.name[: -len(SIDECAR_SUFFIX)] + ".js")
        try:
            sc = load(js_path)
        except ValueError:
            continue
        for entry in sc.entries:
            if entry.pattern_id == pattern_id:
                return js_path, entry
    return None


def most_recent_device(project_patterns_dir: Path) -> str | None:
    """The device most recently deployed to across a project's sidecars.

    For a brand-new pattern with no history of its own, the project's last-used
    device is a better guess than a manifest field that would go stale.
    """
    best: tuple[datetime, str] | None = None
    if not project_patterns_dir.exists():
        return None
    for path in sorted(project_patterns_dir.glob(f"*{SIDECAR_SUFFIX}")):
        js_path = path.with_name(path.name[: -len(SIDECAR_SUFFIX)] + ".js")
        try:
            front = load(js_path).front
        except ValueError:
            continue
        if front is None:
            continue
        if best is None or front.deployed_at > best[0]:
            best = (front.deployed_at, front.device_id)
    return best[1] if best else None
