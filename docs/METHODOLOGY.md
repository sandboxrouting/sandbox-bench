# Methodology

> Status: **draft for v0.1**. This document is versioned together with the harness. If they disagree, the code wins, and the disagreement is a bug that someone should file.

## 1. How the benchmark works

sandbox-bench produces two kinds of results.

1. **The probe suite: what a sandbox can do.**
   - The suite is a fixed, versioned set of **probes**. Each probe is a pass/fail challenge, such as "fork keeps memory" or "egress block is enforced", and an automated **verifier** decides the outcome.
   - A configuration's **probe score** is its pass rate. The main leaderboard is ranked by it.
2. **Performance boards: how fast and how cheap.**
   - These are numeric leaderboards for start time, resume, fork, file I/O, cost and so on.
   - **A configuration appears on a board only if it passes that board's gating probe.** For example, you can't rank on fork speed without a fork that works.

Each provider's extras turn into probes. A feature only one provider has today still earns that provider points. Once others support it, it also becomes a speed race.

## 2. Vocabulary

| Term | Definition |
|---|---|
| **Provider** | A company or product, e.g. E2B or Daytona. |
| **Configuration** | **The unit we rank:** provider + sandbox type + plan + region + size, e.g. `daytona/container/tier1/us/2c4g`. Daytona containers and Daytona Linux VMs are different products, so they are separate configurations. |
| **Probe** | A pass/fail challenge. It has a setup, an action and a verifier, and it lives in `probes/<category>/<name>/`. |
| **Verifier** | The automated check that decides a probe's outcome, e.g. "same PID alive, same memory hash, counter continued". |
| **Suite** | A versioned set of probes, e.g. `core-v0.1`. Probe scores are only compared within the same suite version. |
| **Category** | A group of probes: `lifecycle`, `state`, `environment` and, later, `specialized`. |
| **Metric** | A number measured on a performance board, e.g. `resume_ms`. |
| **Board** | A leaderboard for one or more metrics. Each board is gated by one probe. |
| **Start mode** | How a sandbox came up: `cold` (fresh boot) or `warm` (pre-started pool or memory restore). The harness detects it and shows it as a column. |
| **Division** | `default`, `optimized` or `submitted` ([GOVERNANCE](GOVERNANCE.md#divisions)). Divisions are never mixed in one ranking. |
| **Sample / Run** | A sample is one measurement. A run is one execution of the suite and boards, with a `run_id` and a manifest. |

## 3. Sandbox spec

- **Size:** 2 vCPU / 4 GiB RAM / ≥10 GiB disk.
  - Where a provider has fixed shapes, we use the nearest shape at or above this and record the actual shape.
  - A provider joins once its account (free tier or donated credits) can run this size.
- **Environment:** there are two settings, and both are measured.
  - **Default environment:** whatever the provider gives you without configuration. It is used by most probes and boards.
  - **Pinned toolset:** our reference software set, defined in `toolset/v1.yaml`: Python 3.12, Node 22, git, gcc and make, at pinned versions. Each provider installs it with **its own native mechanism**, such as a Dockerfile build, a template, or a setup script followed by a snapshot. A verifier confirms the versions. We provide `toolset/Dockerfile` and `toolset/setup.sh` as reference implementations. The point is that "same software" is checked, not assumed, without forcing one image format on providers that can't accept it.
- **Region:** the provider region closest to the runner, recorded per sample.
- **Bring your own tools:** anything a verifier or workload needs is uploaded before the clock starts, as the `sbx-helper` binary or a pinned binary. Results therefore never depend on what a default image happens to contain.

## 4. Probe suite: `core-v0.1`

| Category | Probe | Passes when |
|---|---|---|
| **lifecycle** | `create-exec` | A new 2c4g sandbox runs a command and returns the expected output |
| | `file-roundtrip` | A 10 MiB random file is written, then read back with a matching SHA-256 |
| | `toolset` | A sandbox started from the provider's pinned-toolset environment reports the exact versions in `toolset/v1.yaml` |
| | `session-1h` | A sandbox is still alive and responsive after 1 hour. This probe runs weekly. |
| **state** | `snapshot-keeps-files` | After snapshot and restore, a 64 MiB file has the same hash |
| | `snapshot-keeps-memory` | After snapshot and restore, the helper process is alive with the same PID and memory hash, and its counter continued |
| | `pause-keeps-files` | After pause and resume, the file hash matches |
| | `pause-keeps-memory` | After pause and resume, the helper process is alive with the same PID and memory hash, and its counter continued |
| | `fork-keeps-memory` | A fork of a running sandbox contains the parent's live helper process and memory state |
| | `fork-isolation-x10` | 10 forks are all up. A marker written in one fork is invisible to the parent and the other forks. |
| **environment** | `dockerfile` | The provider builds and starts a sandbox directly from `toolset/Dockerfile` |
| | `internet` | A pinned file downloads from a public CDN with a matching hash |
| | `egress-block` | With deny-all egress configured, an outbound connection fails |
| | `exposed-port` | An HTTP server inside the sandbox is reachable from the runner through the provider's URL or port |
| | `docker-in-sandbox` | `docker run` of a pinned image succeeds inside the sandbox |

**Outcomes:**
- **pass (✓).**
- **fail (✗):** the probe was attempted and the verifier rejected the result, or an error occurred.
- **unsupported (—):** the adapter declares that the feature doesn't exist.

Both fail and unsupported score 0. They are shown differently so readers can tell a broken feature from a missing one.

**Any public mechanism counts.** For example, a fork built from a memory snapshot plus N restores passes `fork-keeps-memory` if the verifier is satisfied. The mechanism is recorded in the configuration metadata.

**Pass rule:** in the rolling 7-day window, a probe counts as passed when **≥ 90% of its attempts succeed**. Each cell shows the success rate, so flaky features are visible.

**Probe score:**
- The score is the **mean of the per-category pass rates**, so each category carries equal weight however many probes it has.
- The raw count is shown next to it, e.g. "86% · 13/15".

**Next categories** (each a suite minor version):
- `specialized`: `chromium-cdp`, `desktop-screenshot`, `gpu-matmul`, `arm64`, `macos`, `windows`.
- Further `state` probes: `idle-autowake`, `resume-after-24h`.

## 5. Performance boards

All timings are **client-side wall clock** taken with a monotonic clock in the harness, never from timings the provider reports. "Ready" always means **a command ran successfully inside the sandbox**, not "the API returned an ID".

| Board | Metric | Clock starts | Clock stops | Gated by |
|---|---|---|---|---|
| **Start** | `start_ms` | Before the create call (default environment) | The first `echo ready` returns exit code 0 | `create-exec` |
| **Start with toolset** | `start_toolset_ms` | Before the create call (pinned-toolset environment) | The first successful exec | `toolset` |
| | `toolset_setup_s` (one-time) | Before building or registering the environment | It is usable | `toolset` |
| **Exec round-trip** | `exec_rtt_ms` | Before the exec call | It returns. This is the median of 20 sequential `true` execs. | `create-exec` |
| **File I/O** | `file_write_mbps`, `file_read_mbps` | Before the 10 MiB write or read | It completes | `file-roundtrip` |
| **Snapshot & restore** | `snapshot_ms` | Before the snapshot call | The snapshot is usable | `snapshot-keeps-files` |
| | `restore_ms` | Before create-from-snapshot | The first successful exec | `snapshot-keeps-files` |
| **Pause & resume** | `pause_ms` | Before the pause call | The call returns or the state reads paused | `pause-keeps-files` |
| | `resume_ms` | Before the resume call | The first successful exec | `pause-keeps-files` |
| **Fork** | `fork_ms` | Before the fork call | The first successful exec in the child | `fork-isolation-x10` |
| | `fork10_ms` | Before the fork call with N = 10 | All 10 children have run a command | `fork-isolation-x10` |
| **Cost** | `usd_per_hour_full`, `usd_per_hour_idle` | List-price model (§9) | — | `create-exec` |

**Extra columns:**
- **Memory column.** Every state board shows whether the matching `*-keeps-memory` probe passes, and a "memory kept only" filter re-ranks the board. This keeps a fast files-only resume from being mistaken for a full one.
- **Start mode.** At the first exec, the helper reads the age of PID 1.
  - If PID 1 is younger than the time since the create call, the start is `cold`. Otherwise it is `warm`.
  - The adapter declares whether a warm start means `pool` or `restore`.
  - If the detected mode doesn't match the declared one, the result is flagged.

**Later boards:** `workloads` (repo clone/install/test, CPU, disk, network, Terminal-Bench via Harbor), `scale` (burst N = 10/50/100 and sustained creates per minute; success rate is reported as capacity, separate from latency), `gpu`, and `browser`.

## 6. The helper

`sbx-helper` is a small static binary (Go, linux amd64/arm64) built from `helper/` in this repo. The harness uploads it before the clock starts. Because verifiers never rely on Python or any other software in the image, they work on any image.

| Subcommand | Used by |
|---|---|
| `hold`: allocates a 256 MiB random buffer and keeps a monotonic counter running in the background | `*-keeps-memory` |
| `inspect`: reports PID, buffer hash and counter | `*-keeps-memory`, `fork-keeps-memory` |
| `mark` / `check`: writes and looks for isolation markers | `fork-isolation-x10` |
| `toolset-check`: compares installed versions against `toolset/v1.yaml` | `toolset`, `dockerfile` |
| `start-age`: reports the age of PID 1 | start-mode detection |

## 7. Measurement protocol

1. **Runner.** Development runs happen locally. Published runs come from a fixed machine in a declared region (v0.1: US-East; v0.2: US-East, EU-West and AP-Southeast). Its spec and region are recorded in each run manifest.
2. **Interleaving.** Iterations go round-robin across configurations, with the order **shuffled each round**.
3. **One operation in flight.** Probes and boards run strictly sequentially, one sandbox operation at a time across the whole runner, so providers never compete for the client's CPU or network. Only the `scale` boards run operations concurrently, by design.
4. **Iterations per run:**
   - **Speed boards:** n = 30 per configuration, plus 3 warm-up iterations. Warm-up samples are recorded and flagged.
   - **State boards:** n = 10.
   - **Probes:** 3 attempts each, except `session-1h`, which runs weekly.
   - **Window:** boards and probe pass rates aggregate a **rolling 7-day window**.
5. **Cadence.** v0.1 runs daily; v0.2 runs every 6 hours.
6. **Timeouts.** Create, restore, resume and fork time out at 120 s, and exec at 60 s. A timeout is a failure, never a sample capped at the timeout.
7. **Error attribution.**
   - **Provider errors** (5xx, timeouts, wrong results, rate limits under documented-normal usage) count as failures.
   - **Harness errors** (our bug, our expired credentials, our exhausted credits) are excluded and logged in the run report.
8. **Cleanup.** Every sandbox is tagged `sandbox-bench/<run_id>`, and a reaper destroys leftovers after each run.
9. **Accounts.** Each configuration runs on free-tier credits or credits the provider has given us, recorded in its metadata ([GOVERNANCE](GOVERNANCE.md#accounts-and-credits)).

## 8. Rankings and statistics

**Main leaderboard:**
- One row per configuration, **ranked by probe score**. Equal scores share a rank.
- Columns: probe score with the pass count, the headline board medians (start, start with toolset, resume, fork×10) with their start-mode and memory tags, and $/h.
- Every column can be sorted.

**Board rankings:**
- Ordered by median.
- Configurations whose bootstrap 95% CIs for the median overlap share a **rank band** ("statistically tied").

**Per-metric detail:**
- n, success rate, p50, p90, p99 (p99 only when n ≥ 100), min and max.
- An ECDF chart, with every sample available to view.

**Probe matrix:** configurations × probes, showing ✓ / ✗ / — with success rates. Every cell links to its raw attempts.

**Freshness:** every number shows its date window. A configuration with no successful run in 14 days is marked `stale`.

## 9. Cost

1. **List-price model.** `pricing/pricing.yaml` stores every rate with its source URL and the date it was checked. From it we compute:
   - `usd_per_hour_full`: 2c4g at 100% CPU.
   - `usd_per_hour_idle`: 2c4g at 10% CPU, a typical agent waiting on an LLM. This differs from the full figure for providers that bill only active CPU.
   - Platform fees (monthly minimums), shown separately.
2. **Measured cost** (v0.2 onward). After a workload, we read the provider's usage API or the invoice delta and report e.g. `$ per 1000 starts`. Where usage can't be read back, the result is marked `estimated`.

Each cost page notes what makes prices hard to compare: how a "core" is defined, fixed CPU:RAM ratios, per-creation fees, billing minimums and snapshot storage.

## 10. Versioning

- **Suite version** (`core-vX.Y`):
  - Adding or changing a probe bumps it.
  - Probe scores are compared only within one suite version.
  - The site shows the current suite and keeps older suites' results archived.
- **Harness version** (semver):
  - A change to a timing boundary, a verifier or the scoring bumps the minor version.
  - A change that breaks comparability bumps the major version.
  - Every bump is logged in `CHANGELOG.md`.
- **SDK versions** are pinned, and upgrades go through PRs. An SDK bump that moves a metric by more than 20% is called out in the run report.
- **New categories, scoring changes and timing-boundary changes** follow the RFC process in [GOVERNANCE.md](GOVERNANCE.md#changing-the-benchmark).
