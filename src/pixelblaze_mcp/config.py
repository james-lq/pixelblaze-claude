"""Call-time configuration: the device registry and per-project manifests.

Nothing here is read at import time. `devices.toml` and each
`projects/<name>/project.toml` are parsed on every call that needs them, so
editing either takes effect without restarting the MCP server. The files are
tiny; re-reading them is cheaper than any cache-invalidation story.

Both files are read and written through `tomlkit`, which keeps comments,
key order, and formatting intact across a tool-driven edit. The rule is that
tooling only touches keys it owns (`name` and `host` in the registry; nothing
in a project manifest today).
"""

import os
import re
from pathlib import Path
from typing import Any, Literal

import tomlkit
from pydantic import BaseModel, ConfigDict, ValidationError, field_validator

WORKSPACE_ROOT: Path = Path(__file__).parent.parent.parent
DOCS_DIR: Path = WORKSPACE_ROOT / "docs" / "pixelblaze"
DEVICES_FILE: Path = WORKSPACE_ROOT / "devices.toml"
PROJECTS_DIR: Path = WORKSPACE_ROOT / "projects"

PROJECT_MANIFEST_NAME = "project.toml"


# --- Chip IDs -------------------------------------------------------------
#
# The device's immutable hardware ID, reported as an integer in the `chipId`
# field of the getConfig response and sent in the UDP discovery beacon. The
# canonical written form, used for registry table keys and everywhere the ID
# is displayed, is `0x` followed by 8 upper-case hex digits.

_CHIP_ID_RE = re.compile(r"^(?:0[xX])?([0-9a-fA-F]{1,8})$")
_MAX_CHIP_ID = 0xFFFFFFFF


def format_chip_id(value: int | str) -> str:
    """Canonical chip ID form: `0x` plus 8 upper-case hex digits.

    Accepts an int (as the device reports it), a `0x`-prefixed hex string, a
    bare hex string containing at least one letter, or an all-digit string,
    which is read as decimal — that being the form `chipId` arrives in. Write
    `0x` in front of an all-digit value to have it read as hex instead.
    """
    if isinstance(value, bool):  # bool is an int subclass; never a chip ID
        raise ValueError(f"Not a chip ID: {value!r}")
    if isinstance(value, int):
        n = value
    else:
        text = str(value).strip()
        m = _CHIP_ID_RE.match(text)
        if not m:
            raise ValueError(
                f"Not a chip ID: {value!r}. Expected an integer, `0x` plus up to "
                "8 hex digits, or a decimal string."
            )
        digits = m.group(1)
        n = int(digits, 10) if text.isdigit() else int(digits, 16)
    if not 0 <= n <= _MAX_CHIP_ID:
        raise ValueError(f"Chip ID out of range for a 32-bit value: {value!r}")
    return f"0x{n:08X}"


def is_chip_id(text: str) -> bool:
    """True if `text` could be a written chip ID, ambiguity with names aside."""
    try:
        format_chip_id(text)
    except ValueError:
        return False
    return True


# --- Device registry ------------------------------------------------------


class Device(BaseModel):
    """One entry in `devices.toml`, or an ad-hoc device named by host."""

    model_config = ConfigDict(extra="forbid")

    name: str | None = None
    host: str
    notes: str = ""

    # Not read from the file: the registry injects the table key, and an
    # ad-hoc device (a bare host passed to a tool) has neither.
    chip_id: str | None = None
    ad_hoc: bool = False

    @property
    def label(self) -> str:
        """How this device is named in tool output and error messages."""
        if self.ad_hoc:
            return f"{self.host} (ad-hoc)"
        parts = [p for p in (self.name, self.chip_id) if p]
        return f"{' '.join(parts)} at {self.host}" if parts else self.host


class Registry:
    """The parsed `devices.toml`, keyed by canonical chip ID.

    Holds the underlying `tomlkit` document so that tools which refresh
    `name` / `host` can write the file back with its comments intact.
    """

    def __init__(self, doc: tomlkit.TOMLDocument, devices: dict[str, Device], path: Path):
        self.doc = doc
        self.devices = devices
        self.path = path

    def __contains__(self, chip_id: str) -> bool:
        return chip_id in self.devices

    def __len__(self) -> int:
        return len(self.devices)

    def summary(self) -> str:
        """One line per registered device, for error messages and listings."""
        if not self.devices:
            return f"(no devices registered in {self.path.name})"
        return "\n".join(f"  {d.label}" for d in self.devices.values())

    def set_fields(self, chip_id: str, *, name: str | None = None, host: str | None = None) -> bool:
        """Update the `name` / `host` of one entry, creating it if absent.

        Only those two keys are touched; everything else in the document,
        comments included, is left exactly as it was. Returns True if the
        document actually changed.
        """
        table = self.doc.setdefault("devices", tomlkit.table(is_super_table=True))
        changed = False
        if chip_id not in table:
            entry = tomlkit.table()
            table[chip_id] = entry
            changed = True
        entry = table[chip_id]
        for key, value in (("name", name), ("host", host)):
            if value is not None and entry.get(key) != value:
                entry[key] = value
                changed = True
        if changed:
            self.devices = _devices_from_doc(self.doc, self.path)
        return changed

    def save(self) -> None:
        self.path.write_text(tomlkit.dumps(self.doc), encoding="utf-8")


def _devices_from_doc(doc: Any, path: Path) -> dict[str, Device]:
    raw = doc.unwrap().get("devices", {}) if hasattr(doc, "unwrap") else doc.get("devices", {})
    devices: dict[str, Device] = {}
    for key, entry in raw.items():
        if not isinstance(entry, dict):
            raise ValueError(f"{path.name}: [devices.{key}] must be a table")
        try:
            chip_id = format_chip_id(key)
        except ValueError as e:
            raise ValueError(
                f"{path.name}: [devices.{key}] is not a valid chip ID. {e} "
                "Run pixelblaze_discover_devices to fill in a device's real ID."
            ) from e
        try:
            devices[chip_id] = Device(chip_id=chip_id, **entry)
        except ValidationError as e:
            raise ValueError(f"{path.name}: [devices.{key}] is not valid.\n{e}") from e
    return devices


def load_devices() -> Registry:
    """Parse `devices.toml`. A missing file is an empty registry, not an error."""
    if not DEVICES_FILE.exists():
        return Registry(tomlkit.document(), {}, DEVICES_FILE)
    try:
        doc = tomlkit.parse(DEVICES_FILE.read_text(encoding="utf-8"))
    except Exception as e:
        raise ValueError(f"Could not parse {DEVICES_FILE}: {e}") from e
    return Registry(doc, _devices_from_doc(doc, DEVICES_FILE), DEVICES_FILE)


# --- Project manifests ----------------------------------------------------

# Characters that are illegal in filenames on Windows (a superset of macOS and
# Linux). The name prefix ends up in a device display name that has to map back
# to a filename, so it is held to the same rule.
_ILLEGAL_FILENAME_CHARS = re.compile(r'[<>:"/\\|?*\x00-\x1f]')


class ProjectManifest(BaseModel):
    """The contents of `project.toml`. Every key has a default, so an empty
    or absent manifest is valid."""

    model_config = ConfigDict(extra="forbid")

    pattern_name_prefix: str | None = None  # None means "use the folder name"
    ordinals: Literal["auto", "none"] = "auto"
    pixel_map: str | None = None
    preview_capture: bool = True

    @field_validator("pattern_name_prefix")
    @classmethod
    def _filename_safe(cls, v: str | None) -> str | None:
        if v and _ILLEGAL_FILENAME_CHARS.search(v):
            raise ValueError(
                "pattern_name_prefix must be filename-safe: it becomes part of the "
                "device display name, which has to map back to a local filename"
            )
        return v


class Project(BaseModel):
    """A project folder plus its resolved manifest settings."""

    model_config = ConfigDict(extra="forbid")

    name: str  # the folder name under projects/, which is the project's identity
    path: Path
    manifest: ProjectManifest

    @property
    def patterns_dir(self) -> Path:
        return self.path / "patterns"

    @property
    def pattern_name_prefix(self) -> str:
        """Prefix for on-device display names. Defaults to the folder name;
        an explicit empty string in the manifest means no prefix at all."""
        prefix = self.manifest.pattern_name_prefix
        return self.name if prefix is None else prefix

    @property
    def ordinals(self) -> str:
        return self.manifest.ordinals

    @property
    def preview_capture(self) -> bool:
        return self.manifest.preview_capture

    @property
    def pixel_map_path(self) -> Path | None:
        """The project-level pixel map, if the manifest declares one."""
        if not self.manifest.pixel_map:
            return None
        return self.path / self.manifest.pixel_map


def list_projects() -> list[str]:
    """Folder names under `projects/`, sorted."""
    if not PROJECTS_DIR.exists():
        return []
    return sorted(p.name for p in PROJECTS_DIR.iterdir() if p.is_dir())


def load_project(name: str) -> Project:
    """Parse `projects/<name>/project.toml`. A missing manifest is all defaults."""
    path = PROJECTS_DIR / name
    if not path.is_dir():
        known = ", ".join(list_projects()) or "(none)"
        raise ValueError(f"No project folder 'projects/{name}'. Known projects: {known}")

    manifest_path = path / PROJECT_MANIFEST_NAME
    data: dict[str, Any] = {}
    if manifest_path.exists():
        try:
            data = tomlkit.parse(manifest_path.read_text(encoding="utf-8")).unwrap()
        except Exception as e:
            raise ValueError(f"Could not parse {manifest_path}: {e}") from e
    try:
        manifest = ProjectManifest(**data)
    except ValidationError as e:
        raise ValueError(f"{manifest_path} is not valid.\n{e}") from e
    return Project(name=name, path=path, manifest=manifest)


def project_for_path(file_path: Path) -> Project:
    """The project owning a file, found by walking up to the `projects/` child.

    A file path is the primary handle for local-side operations, and it implies
    its project, so tools that take one do not also need a `project` argument.
    """
    resolved = file_path.resolve()
    projects_root = PROJECTS_DIR.resolve()
    for parent in resolved.parents:
        if parent.parent == projects_root:
            return load_project(parent.name)
    raise ValueError(
        f"{file_path} is not inside a project folder under {PROJECTS_DIR}. "
        f"Known projects: {', '.join(list_projects()) or '(none)'}"
    )


def resolve_path(file_path: str | Path) -> Path:
    """Resolve a tool's `file_path` argument; relative paths come off the
    workspace root (the folder holding `devices.toml`)."""
    path = Path(file_path)
    return path if path.is_absolute() else WORKSPACE_ROOT / path


# --- Device resolution ----------------------------------------------------

# An ad-hoc device is recognised by looking like a network address rather than
# a name: an IPv4 address, or a dotted hostname such as `pb.local`. A bare
# single-label string is treated as a display name that failed to match, which
# gives "unknown device, here is the registry" instead of a connection timeout.
_HOSTNAME_RE = re.compile(r"^[A-Za-z0-9]([A-Za-z0-9\-]*[A-Za-z0-9])?(\.[A-Za-z0-9\-]+)+$")


def _looks_like_host(text: str) -> bool:
    return bool(_HOSTNAME_RE.match(text.strip()))


def resolve_device(
    device: str | None = None,
    *,
    registry: Registry | None = None,
    project: Project | None = None,
) -> Device:
    """Find the device a tool call should target.

    `device` accepts, in this order: a chip ID; a display name, case-insensitive;
    a host already in the registry; or a literal IP or dotted hostname, which is
    used as an ad-hoc device with no ID verification.

    Falling back when `device` is omitted needs the pattern sidecar, which
    arrives in phase 2 of plan 01: the pattern's last device, then the project's
    most recently deployed one. Until then an omitted `device` is an error
    listing what is registered.
    """
    registry = registry or load_devices()

    if device is None:
        where = f" for project '{project.name}'" if project else ""
        raise ValueError(
            f"No device specified{where}. Pass `device` as a chip ID, a display name, "
            f"or an IP address. Registered devices:\n{registry.summary()}"
        )

    text = device.strip()
    if not text:
        raise ValueError("`device` is empty. Pass a chip ID, a display name, or an IP address.")

    # 1. Chip ID, in any accepted written form.
    if is_chip_id(text):
        chip_id = format_chip_id(text)
        if chip_id in registry.devices:
            return registry.devices[chip_id]
        raise ValueError(
            f"No device with chip ID {chip_id} in {registry.path.name}. Registered devices:\n"
            f"{registry.summary()}"
        )

    # 2. Display name, case-insensitive. Ambiguity is an error, not a guess.
    matches = [d for d in registry.devices.values() if d.name and d.name.lower() == text.lower()]
    if len(matches) > 1:
        ids = ", ".join(d.chip_id or "?" for d in matches)
        raise ValueError(
            f"'{device}' matches more than one registered device ({ids}). "
            "Use the chip ID instead."
        )
    if matches:
        return matches[0]

    # 3. A host already in the registry resolves to that entry, so it still gets
    #    chip ID verification rather than being treated as an unknown box.
    for d in registry.devices.values():
        if d.host.lower() == text.lower():
            return d

    # 4. An unregistered address: ad-hoc, used as given and never verified.
    if _looks_like_host(text):
        return Device(host=text, ad_hoc=True)

    raise ValueError(
        f"Unknown device '{device}'. Pass a chip ID, a registered display name, "
        f"or an IP address. Registered devices:\n{registry.summary()}"
    )


# --- Offline mode ---------------------------------------------------------
#
# Still a workspace-global flag file. Plan 01 section 8.2 leaves the question of
# making this per-device open; nothing in phase 1 depends on the answer.

_OFFLINE_FLAG: Path = WORKSPACE_ROOT / ".pixelblaze_offline"


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
