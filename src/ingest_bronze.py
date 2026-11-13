"""Bronze layer: store raw CFPB downloads exactly as received.

This is the "Load" step of ELT. Files placed in data/landing/ are copied,
byte for byte, into data/bronze/<source>/<YYYY-MM-DD>/ together with a manifest that
records each file's size and SHA-256 checksum. Nothing is cleaned or changed
here, so every later result can be traced back to the original file.

Sources (kept in separate folders so they are never mixed):
    narratives  monthly files from the CFPB narratives archive (has complaint text)
    live        the current full database download (no complaint text)

Usage:
    python -m src.ingest_bronze --source narratives
    python -m src.ingest_bronze --source live
"""

import argparse
import hashlib
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path

ALLOWED_SUFFIXES = {".zip", ".csv", ".json"}

SOURCES = {
    "narratives": "CFPB Consumer Complaint Database narratives archive (monthly files)",
    "live": "CFPB Consumer Complaint Database full download (no narratives)",
}


def sha256_of(path: Path, block_size: int = 1024 * 1024) -> str:
    """Checksum a file in blocks so large files don't fill memory."""
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(block_size), b""):
            digest.update(block)
    return digest.hexdigest()


def known_checksums(bronze_dir: Path) -> set:
    """Checksums of every file already stored in bronze (from all manifests)."""
    checksums = set()
    for manifest in bronze_dir.rglob("manifest.json"):
        for entry in json.loads(manifest.read_text(encoding="utf-8"))["files"]:
            checksums.add(entry["sha256"])
    return checksums


def ingest(landing_dir: Path, bronze_dir: Path, source: str, today: str | None = None) -> list:
    """Copy new landing files into bronze/<source>/<today>/. Returns manifest entries added."""
    if source not in SOURCES:
        raise ValueError(f"Unknown source {source!r}; choose from {sorted(SOURCES)}")
    today = today or datetime.now(timezone.utc).strftime("%Y-%m-%d")
    candidates = sorted(p for p in landing_dir.iterdir() if p.is_file() and p.suffix.lower() in ALLOWED_SUFFIXES)
    if not candidates:
        print(f"No .zip/.csv/.json files found in {landing_dir}")
        return []

    seen = known_checksums(bronze_dir)
    target = bronze_dir / source / today
    manifest_path = target / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.exists() else {"batch": today, "source": source, "files": []}

    added = []
    for src in candidates:
        checksum = sha256_of(src)
        if checksum in seen:
            print(f"Skipped (already in bronze): {src.name}")
            continue
        target.mkdir(parents=True, exist_ok=True)
        dest = target / src.name
        shutil.copy2(src, dest)
        if sha256_of(dest) != checksum:
            raise IOError(f"Checksum mismatch after copying {src.name}")
        entry = {
            "file": src.name,
            "size_bytes": src.stat().st_size,
            "sha256": checksum,
            "ingested_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "source": SOURCES[source],
        }
        manifest["files"].append(entry)
        added.append(entry)
        seen.add(checksum)
        print(f"Stored: {src.name} ({entry['size_bytes'] / 1e6:.1f} MB)")

    if added:
        manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
        print(f"Manifest written: {manifest_path}")
    return added


def main():
    parser = argparse.ArgumentParser(description="Copy raw CFPB files into the bronze layer.")
    parser.add_argument("--source", required=True, choices=sorted(SOURCES), help="Where the files in landing came from")
    parser.add_argument("--landing", default="data/landing", type=Path)
    parser.add_argument("--bronze", default="data/bronze", type=Path)
    args = parser.parse_args()
    args.bronze.mkdir(parents=True, exist_ok=True)
    ingest(args.landing, args.bronze, args.source)


if __name__ == "__main__":
    main()
