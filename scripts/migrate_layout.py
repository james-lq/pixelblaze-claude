#!/usr/bin/env python
"""Migrate pattern files from the in-file metadata block to `.sidecar.toml`.

A one-off from the move to per-pattern sidecars. For each pattern file in a project:

  * with `--device <id>`, the file's recorded Pattern ID and `@deployed` /
    `@deployed-hash` become a single `deployment_history` entry naming that
    device, and the header line is reduced to the pattern name;
  * without one, the metadata block and the header's Pattern ID are stripped and
    **no sidecar is written** — the pattern gets a fresh ID on its next deploy.
    Reconstructing history for a file whose device is unknown is not worth a
    special case, and a sidecar entry with an unknown device ID is exactly the
    complexity every future consumer would have to handle.

Safe to run more than once: a file already migrated is skipped, so projects can
be done as their devices become known. Delete this script once every project is
through.

Usage:
    uv run python scripts/migrate_layout.py --device 0x00AC056C H26-Finale test-pattern
    uv run python scripts/migrate_layout.py layered-acrylic sound-level-meter
    uv run python scripts/migrate_layout.py --all --dry-run
"""

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from pixelblaze_mcp import sidecar as sidecar_mod  # noqa: E402
from pixelblaze_mcp.config import (  # noqa: E402
    format_chip_id,
    list_projects,
    load_devices,
    load_project,
)
from pixelblaze_mcp.pattern_file import (  # noqa: E402
    has_legacy_block,
    parse_legacy_block,
    strip_legacy_block,
    write_pattern_file,
)


def _parse_deployed_at(text: str | None) -> datetime | None:
    """The `@deployed:` stamp, which was written as `%Y-%m-%dT%H:%M:%SZ`."""
    if not text or text == "(pending)":
        return None
    try:
        return datetime.strptime(text, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def migrate_file(path: Path, device_id: str | None, device_name: str | None, dry_run: bool) -> str:
    """Migrate one pattern file. Returns a one-word outcome for reporting."""
    content = path.read_text(encoding="utf-8")

    if not has_legacy_block(content):
        return "already-migrated"

    legacy = parse_legacy_block(content)
    code = strip_legacy_block(content)
    # The header's name, else the filename stem, becomes the name-only header.
    name = legacy["name"] or path.stem
    # Drop the old `<name> — Pattern ID: <id>` line; write_pattern_file adds the
    # name-only one back.
    body = code
    if legacy["pattern_id"]:
        lines = code.splitlines()
        if lines and "Pattern ID:" in lines[0]:
            body = "\n".join(lines[1:]).lstrip("\n")

    pattern_id = legacy["pattern_id"]
    deployed_at = _parse_deployed_at(legacy["deployed_at"])
    writes_sidecar = bool(device_id and pattern_id and pattern_id != "(pending)" and deployed_at)

    if dry_run:
        return "would-migrate+sidecar" if writes_sidecar else "would-migrate"

    write_pattern_file(path, body, name)

    if not writes_sidecar:
        return "migrated (no sidecar)"

    sc = sidecar_mod.load(path)
    sc.record(
        device_id=device_id,
        device_name=device_name,
        pattern_id=pattern_id,
        # The recorded hash covered the code without the metadata block, which
        # is what the file now holds minus the rewritten header line. Re-hash
        # what was actually written so the file does not read as modified for a
        # reason that is purely cosmetic.
        deployed_hash=sidecar_mod.content_hash(path.read_text(encoding="utf-8")),
        deployed_at=deployed_at,
    )
    sc.save()
    return "migrated+sidecar"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("projects", nargs="*", help="project folder names under projects/")
    parser.add_argument("--all", action="store_true", help="every project")
    parser.add_argument(
        "--device",
        help="chip ID the listed projects' patterns were deployed to; without it, "
        "history is dropped and no sidecar is written",
    )
    parser.add_argument("--dry-run", action="store_true", help="report without writing")
    args = parser.parse_args()

    names = list_projects() if args.all else args.projects
    if not names:
        parser.error("name at least one project, or pass --all")

    device_id = device_name = None
    if args.device:
        device_id = format_chip_id(args.device)
        known = load_devices().devices.get(device_id)
        if known is None:
            print(f"error: {device_id} is not in devices.toml", file=sys.stderr)
            return 1
        device_name = known.name
        print(f"Recording history against {known.label}\n")

    total: dict[str, int] = {}
    for name in names:
        project = load_project(name)
        files = sorted(project.patterns_dir.glob("*.js")) if project.patterns_dir.exists() else []
        # A `.mapper.js` is a pixel map, not a pattern; it has no metadata block
        # and must not gain a sidecar.
        files = [f for f in files if not f.name.endswith(".mapper.js")]
        print(f"{name}: {len(files)} pattern file(s)")
        for path in files:
            outcome = migrate_file(path, device_id, device_name, args.dry_run)
            total[outcome] = total.get(outcome, 0) + 1
            print(f"  {outcome:24} {path.name}")
        print()

    print("Summary: " + ", ".join(f"{v} {k}" for k, v in sorted(total.items())))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
