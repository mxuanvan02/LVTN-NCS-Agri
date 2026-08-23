#!/usr/bin/env python3
"""Regenerate the whole publishable simulation-bundle SHA-256 manifest.

The output manifest excludes itself (a checksum cannot stably contain its own
checksum), the historical initial manifest, virtual environments, caches,
bytecode, and Git metadata. Paths are written relative to the parent Manuscript
directory so `sha256sum -c simulation/SHA256SUMS.final.txt` is unambiguous.
"""
from __future__ import annotations
import hashlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "SHA256SUMS.final.txt"
EXCLUDED_FILES = {"SHA256SUMS.final.txt", "SHA256SUMS.initial.txt"}
EXCLUDED_PARTS = {".venv", ".pytest_cache", "__pycache__", ".git"}


def included(path: Path) -> bool:
    rel = path.relative_to(ROOT)
    return (
        path.is_file()
        and rel.as_posix() not in EXCLUDED_FILES
        and not any(part in EXCLUDED_PARTS for part in rel.parts)
        and path.suffix not in {".pyc", ".pyo"}
    )


def main() -> None:
    rows = []
    for path in sorted(ROOT.rglob("*")):
        if included(path):
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            rows.append(f"{digest}  simulation/{path.relative_to(ROOT).as_posix()}")
    OUT.write_text("\n".join(rows) + "\n", encoding="utf-8")
    print(f"wrote={OUT} entries={len(rows)} self_excluded=true")


if __name__ == "__main__":
    main()
