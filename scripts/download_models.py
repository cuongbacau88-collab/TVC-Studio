#!/usr/bin/env python3
"""Model download plan. This script intentionally cannot download files."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "configs" / "model_manifest.json"


def dry_run() -> int:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    missing = False
    total = 0
    sizes_known = True
    for model in manifest.get("models") or []:
        if model.get("optional"):
            continue
        files = model.get("expected_weight_files") or []
        paths = model.get("expected_paths") or []
        source = model.get("download_source")
        size = model.get("size_bytes")
        if isinstance(size, int):
            total += size
        else:
            sizes_known = False
        print(f"model_id: {model['model_id']}")
        print(f"filename: {', '.join(files) if files else 'UNKNOWN'}")
        print(f"destination: {', '.join(paths) if paths else 'UNKNOWN'}")
        print(f"source: {source or 'MISSING'}")
        if not source:
            print("FAIL: download source missing")
            missing = True
        print()
    print(f"total_size_bytes: {total if sizes_known else 'UNKNOWN'}")
    return 1 if missing else 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", required=True)
    parser.parse_args()
    return dry_run()


if __name__ == "__main__":
    raise SystemExit(main())
