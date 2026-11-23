#!/usr/bin/env python3
"""Bump the app version and sync it across the repo.

Usage: python scripts/bump_version.py [patch|minor|major]  (default: patch)

Writes the new version to:
  version.json          — canonical version
  frontend/package.json — "version" field
  backend/version.py    — VERSION constant
"""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def main() -> None:
    part = sys.argv[1] if len(sys.argv) > 1 else "patch"
    if part not in ("patch", "minor", "major"):
        sys.exit("usage: bump_version.py [patch|minor|major]")

    version_file = ROOT / "version.json"
    current = json.loads(version_file.read_text())["version"]
    major, minor, patch = (int(x) for x in current.split("."))

    if part == "major":
        major, minor, patch = major + 1, 0, 0
    elif part == "minor":
        minor, patch = minor + 1, 0
    else:
        patch += 1
    new = f"{major}.{minor}.{patch}"

    version_file.write_text(json.dumps({"version": new}) + "\n")

    pkg_file = ROOT / "frontend" / "package.json"
    pkg = json.loads(pkg_file.read_text())
    pkg["version"] = new
    pkg_file.write_text(json.dumps(pkg, indent=2) + "\n")

    (ROOT / "backend" / "version.py").write_text(
        f'"""Application version — synced from version.json by scripts/bump_version.py."""\n\nVERSION = "{new}"\n'
    )

    print(f"{current} -> {new}")


if __name__ == "__main__":
    main()
