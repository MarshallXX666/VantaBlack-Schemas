"""Sync StateTransitionEvent contract artifacts from VantaBlack-Engine.

Run this when the Engine bumps the v1 schema or adds new specimens.
Cross-repo single-source-of-truth: schema is authored in the Engine,
mirrored here for cross-repo contract testing.

Usage:
    python scripts/sync_from_engine.py [--engine-path PATH]

Default engine-path: ../VantaBlack-Engine relative to this repo.
"""
from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

ARTIFACTS = [
    ("contracts/state_transition_event.v1.schema.json", "contracts/"),
    (
        "data/contract_specimens/state_transition_event_v1_specimens.jsonl",
        "data/contract_specimens/",
    ),
]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    repo_root = Path(__file__).resolve().parent.parent
    parser.add_argument(
        "--engine-path",
        type=Path,
        default=repo_root.parent / "VantaBlack-Engine",
        help="Path to VantaBlack-Engine repo",
    )
    args = parser.parse_args()

    if not args.engine_path.exists():
        print(f"ERROR: engine path does not exist: {args.engine_path}", file=sys.stderr)
        return 1

    for src_rel, dest_rel in ARTIFACTS:
        src = args.engine_path / src_rel
        dest_dir = repo_root / dest_rel
        if not src.exists():
            print(f"WARN: source not found: {src}", file=sys.stderr)
            continue
        dest_dir.mkdir(parents=True, exist_ok=True)
        dest = dest_dir / src.name
        shutil.copy2(src, dest)
        print(f"COPIED: {src} -> {dest}")

    print("\nDone. Re-run contract tests: pytest tests/test_state_transition_event_contract.py")
    return 0


if __name__ == "__main__":
    sys.exit(main())
