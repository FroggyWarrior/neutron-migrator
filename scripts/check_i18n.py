#!/usr/bin/env python3
"""Validate translation files: parseable JSON, same keys as en.json, no empty values."""
from __future__ import annotations

import json
import sys
from pathlib import Path

FOLDER = Path(__file__).resolve().parents[1] / "src" / "neutron_migrator" / "assets" / "i18n"


def load(path: Path) -> dict:
    return json.loads(path.read_text("utf-8-sig"))


def main() -> None:
    try:
        base = set(load(FOLDER / "en.json"))
    except Exception as exc:
        sys.exit(f"en.json is not usable: {exc}")

    problems = 0
    for path in sorted(FOLDER.glob("*.json")):
        try:
            data = load(path)
        except Exception as exc:
            print(f"{path.name:10} INVALID JSON -> {exc}")
            problems += 1
            continue
        missing = sorted(base - set(data))
        extra = sorted(set(data) - base)
        empty = sorted(k for k, v in data.items() if not str(v).strip())
        ok = not (missing or extra or empty)
        print(f"{path.name:10} {'OK' if ok else 'FAIL'}  ({len(data)} keys)")
        for title, items in (("missing", missing), ("extra", extra), ("empty", empty)):
            if items:
                print(f"   {title}: {items}")
        problems += 0 if ok else 1
    sys.exit(1 if problems else 0)


if __name__ == "__main__":
    main()