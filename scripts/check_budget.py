"""Fail when the harness grows past its line budget (ROADMAP, "Scope creep").

Counts non-blank, non-comment lines in src/sandbox_bench, excluding provider adapters and
probe actions: those grow with the benchmark, the harness shouldn't. The shared probe modules
(probes/__init__.py, probes/guest.py) are harness and count
(docs/decisions/0003-line-budget-counts-shared-probe-code.md).
"""

from __future__ import annotations

import sys
from pathlib import Path

BUDGET = 1800
ROOT = Path(__file__).resolve().parent.parent / "src" / "sandbox_bench"
EXCLUDED = ("providers", "probes")
SHARED = ("probes/__init__.py", "probes/guest.py")


def count(path: Path) -> int:
    lines = (line.strip() for line in path.read_text(encoding="utf-8").splitlines())
    return sum(1 for line in lines if line and not line.startswith("#"))


def main() -> int:
    files = sorted(
        p
        for p in ROOT.rglob("*.py")
        if p.relative_to(ROOT).parts[0] not in EXCLUDED or p.relative_to(ROOT).as_posix() in SHARED
    )
    per_file = {p.relative_to(ROOT).as_posix(): count(p) for p in files}
    total = sum(per_file.values())
    for name, n in sorted(per_file.items(), key=lambda kv: -kv[1]):
        sys.stdout.write(f"{n:6d}  {name}\n")
    sys.stdout.write(f"{total:6d}  total (budget {BUDGET})\n")
    if total > BUDGET:
        sys.stdout.write(f"harness is {total - BUDGET} lines over budget\n")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
