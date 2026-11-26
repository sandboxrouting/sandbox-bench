# 0003. The line budget counts shared probe code, and is 1,800 lines

- **Status:** accepted
- **Date:** 2026-11-26

## Context
The roadmap caps the harness to keep scope from creeping. `scripts/check_budget.py` enforces the cap in CI. It skips `providers/` and `probes/`, because those grow with each provider and probe.

`probes/` also holds two shared modules: `guest.py` (every shell script run inside a sandbox, plus parsers) and `probes/__init__.py` (the `Context` that probes call). They are harness code, about 270 counted lines, and the budget was skipping them. Counting them, the harness is 1,740 lines (2026-11-26); without them, 1,466 against a 1,500 budget.

## Decision
Count the two shared modules, and set the budget to 1,800. Probe action files (`basics.py`, `network.py`, ...) and provider adapters stay uncounted.

## Alternatives
- **Keep skipping them, at 1,500.** No work, but the number understates the harness, and shared code could keep slipping into `probes/` to avoid the cap.
- **Count them and cut the harness back to 1,500.** This keeps the original limit, but means reworking tested code for a number no user sees.

## Consequences
- The budget number is the real size of the harness. There are 60 lines of headroom.
- The 1,500 figure in the roadmap became 1,800.
