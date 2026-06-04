#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Validate a learning resources seed JSON file without Firestore writes."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from mtc_assistant.learning_resources_seed_validator import (  # noqa: E402
    load_resources_payload,
    plan_learning_resources_seed,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Validate a local learning resources seed JSON file. Input may be "
            "a top-level list or an object with a resources list."
        )
    )
    parser.add_argument("--seed", required=True, help="Path to local seed JSON.")
    parser.add_argument("--existing", help="Optional local existing-resource snapshot JSON.")
    args = parser.parse_args(argv)

    try:
        seed_resources = load_resources_payload(_load_json(args.seed))
        existing_resources = load_resources_payload(_load_json(args.existing)) if args.existing else None
        result = plan_learning_resources_seed(seed_resources, existing_resources=existing_resources)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        result = {
            "would_create": [],
            "would_update": [],
            "would_skip": [],
            "would_disable": [],
            "errors": [{"message": str(exc)}],
            "warnings": [],
        }

    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 1 if result["errors"] else 0


def _load_json(path: str):
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)


if __name__ == "__main__":
    raise SystemExit(main())
