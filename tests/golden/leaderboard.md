# sandbox-bench leaderboard (v0.1)

*As of 2026-11-20 · attempts from 2026-11-20 · runner in us-east · 2 vCPU / 4 GiB requested, actual sizes in the tables below*

| # | Provider   | Probes passed                        | Keeps memory on       | Start            | Resume  | Restore | Fork    | $/h running / paused |
|---|------------|--------------------------------------|-----------------------|------------------|---------|---------|---------|----------------------|
| 1 | beta (vm)  | 100% (11 of 11)                      | pause, snapshot, fork | 0.9 s (snapshot) | 0.3 s   | 0.8 s   | 1.1 s   | 0.13 / 0.004         |
| 2 | alpha (vm) | 45% (5 of 11), failing: egress-block | none                  | 1.6 s (cold)     | n/a     | 1.8 s   | n/a     | 0.17 / n/a           |
| - | gamma (vm) | 0% (0 of 11), 11 pending             | none                  | pending          | pending | pending | pending | ?                    |

A probe passes at 9 of its last 10 attempts. Times are medians of the last 10, shown only when the probe behind the column passes. "-" = not ranked yet (a probe has fewer than 10 attempts). "?" = no list price found yet, see `pricing/pricing.yaml`.

### Start

Shown when `create-exec` passes. Ranked with 10 samples, at any size.

| # | Provider   | p50   | p90   | n  | Success | Window     | Plan      | Size           | Region    | API RTT |
|---|------------|-------|-------|----|---------|------------|-----------|----------------|-----------|---------|
| 1 | beta (vm)  | 0.9 s | 0.9 s | 10 | 10/10   | 2026-11-20 | free tier | 2 vCPU / 4 GiB | us-east-1 | 0.06 s  |
| 2 | alpha (vm) | 1.6 s | 1.6 s | 10 | 10/10   | 2026-11-20 | free tier | 2 vCPU / 4 GiB | us-east-1 | -       |

Not shown: gamma (pending).

### Resume

Shown when `pause-keeps-files` passes. Ranked with 10 samples, at 2 vCPU / 4 GiB only.

| # | Provider  | p50   | p90   | n  | Success | Window     | Plan      | Size           | Region    | API RTT |
|---|-----------|-------|-------|----|---------|------------|-----------|----------------|-----------|---------|
| 1 | beta (vm) | 0.3 s | 0.3 s | 10 | 10/10   | 2026-11-20 | free tier | 2 vCPU / 4 GiB | us-east-1 | 0.06 s  |

Not shown: alpha (n/a), gamma (pending).

### Restore

Shown when `snapshot-keeps-files` passes. Ranked with 10 samples, at 2 vCPU / 4 GiB only.

| # | Provider   | p50   | p90   | n  | Success | Window     | Plan      | Size           | Region    | API RTT |
|---|------------|-------|-------|----|---------|------------|-----------|----------------|-----------|---------|
| 1 | beta (vm)  | 0.8 s | 0.8 s | 10 | 10/10   | 2026-11-20 | free tier | 2 vCPU / 4 GiB | us-east-1 | 0.06 s  |
| 2 | alpha (vm) | 1.8 s | 1.8 s | 10 | 10/10   | 2026-11-20 | free tier | 2 vCPU / 4 GiB | us-east-1 | -       |

Not shown: gamma (pending).

### Fork

Shown when `fork-keeps-memory` passes. Ranked with 10 samples, at 2 vCPU / 4 GiB only.

| # | Provider  | p50   | p90   | n  | Success | Window     | Plan      | Size           | Region    | API RTT |
|---|-----------|-------|-------|----|---------|------------|-----------|----------------|-----------|---------|
| 1 | beta (vm) | 1.1 s | 1.1 s | 10 | 10/10   | 2026-11-20 | free tier | 2 vCPU / 4 GiB | us-east-1 | 0.06 s  |

Not shown: alpha (n/a), gamma (pending).

### Exec

Shown when `create-exec` passes. Ranked with 10 samples, at any size.

| # | Provider   | p50    | p90    | n  | Success | Window     | Plan      | Size           | Region    | API RTT |
|---|------------|--------|--------|----|---------|------------|-----------|----------------|-----------|---------|
| 1 | alpha (vm) | 0.04 s | 0.04 s | 10 | 10/10   | 2026-11-20 | free tier | 2 vCPU / 4 GiB | us-east-1 | -       |

Not shown: beta (no samples), gamma (pending).

### Pause

Shown when `pause-keeps-files` passes. Ranked with 10 samples, at any size.

| # | Provider  | p50   | p90   | n  | Success | Window     | Plan      | Size           | Region    | API RTT |
|---|-----------|-------|-------|----|---------|------------|-----------|----------------|-----------|---------|
| 1 | beta (vm) | 0.2 s | 0.2 s | 10 | 10/10   | 2026-11-20 | free tier | 2 vCPU / 4 GiB | us-east-1 | 0.06 s  |

Not shown: alpha (n/a), gamma (pending).

### Snapshot

Shown when `snapshot-keeps-files` passes. Ranked with 10 samples, at any size.

| # | Provider   | p50   | p90   | n  | Success | Window     | Plan      | Size           | Region    | API RTT |
|---|------------|-------|-------|----|---------|------------|-----------|----------------|-----------|---------|
| 1 | alpha (vm) | 368 s | 368 s | 10 | 10/10   | 2026-11-20 | free tier | 2 vCPU / 4 GiB | us-east-1 | -       |

Not shown: beta (no samples), gamma (pending).

## Providers

- **beta (vm)**: Start: snapshot, 0.9 s. Pause: keeps memory, 0.2 s. Snapshot: keeps memory. Fork: keeps memory, 1.1 s (snapshot, then restore).
  Price ($/h running / paused): 0.13 / 0.004, https://beta.example/pricing (checked 2026-11-26).
- **alpha (vm)**: Start: cold, 1.6 s. Pause: not offered. Snapshot: files only, 368 s. Fork: not offered.
  Price ($/h running / paused): 0.17 / n/a (2 x 0.0504 + 4 x 0.0162), https://alpha.example/pricing (checked 2026-11-25). Billed per second.
- **gamma (vm)**: Start: pool, pending. Pause: pending. Snapshot: pending. Fork: pending.

## Failing probes

- **alpha** `egress-block` verified 6/10. Last failure: run `r1`, all attempt 9 (2026-11-20): AssertionError: hash mismatch. Evidence: `{"actual": "xyz", "expected": "abc"}`. Reproduce: `sbx check alpha --probe egress-block`
