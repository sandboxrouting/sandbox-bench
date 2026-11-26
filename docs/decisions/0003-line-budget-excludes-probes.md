# 0003. The line budget doesn't count `probes/`

- **Status:** proposed
- **Date:** 2026-11-26

## Context
The roadmap caps the harness at about 1,500 lines, against scope creep. `scripts/check_budget.py` enforces it in CI, and counts everything in `src/sandbox_bench` except `providers/` and `probes/`, because those grow with each provider and probe.

`probes/` also holds two shared modules: `guest.py` (every shell script run inside a sandbox, plus parsers) and `probes/__init__.py` (the `Context` that probes call). Together they are about 270 counted lines. With them, the harness is about 1,740 lines; without them, 1,466 (on 2026-11-26).

## Decision
Keep the budget at 1,500, measured outside `providers/` and `probes/`. The shared probe modules stay in `probes/`, and this file says so openly.

## Alternatives
- **Count them and raise the budget to 1,800.** This is more honest about the total size, but it moves the line that was set against scope creep.
- **Count them and cut the harness below 1,500.** This would mean merging or dropping features that are already tested.

## Consequences
- The budget number understates the harness by about 270 lines. CONTRIBUTING states this.
- New shared code could slip into `probes/` to avoid the budget. Reviewers should check that anything added there is used only by probes.
