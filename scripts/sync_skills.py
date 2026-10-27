#!/usr/bin/env python3
"""Build self-contained skill folders from the maintained launcher and workflow."""
import argparse
from pathlib import Path
import sys

SKILLS = ("codex-to-codex", "codex-to-claude", "claude-to-claude", "claude-to-codex")
ASSETS = ("scripts/handoff.py", "references/workflow.md", "LICENSE")


def sync(root, check=False):
    failures = []
    for name in SKILLS:
        directory = root / "skills" / name
        if not (directory / "SKILL.md").is_file():
            raise ValueError(f"missing skill: {name}")
        for relative in ASSETS:
            source = root / relative
            target = directory / relative
            expected = source.read_bytes()
            if target.is_file() and not target.is_symlink() and target.read_bytes() == expected:
                continue
            if check:
                failures.append(f"{name}/{relative}")
                continue
            if target.is_symlink():
                raise ValueError(f"refusing symlink destination: {target}")
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(expected)
    return failures


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="fail if bundled assets differ; do not write files")
    args = parser.parse_args()
    try:
        failures = sync(Path(__file__).resolve().parents[1], args.check)
    except (OSError, ValueError) as error:
        print(f"sync: {error}", file=sys.stderr)
        return 1
    if failures:
        print("Bundled skill assets are out of date:\n" + "\n".join(failures), file=sys.stderr)
        print("Run python3 scripts/sync_skills.py before releasing.", file=sys.stderr)
        return 1
    print("Skill assets are current." if args.check else "Skill assets synchronized.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
