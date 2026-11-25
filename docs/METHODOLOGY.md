# Methodology

> Status: **draft for v0.1**. This document is versioned together with the harness. If they disagree, the code wins, and the disagreement is a bug that someone should file.

## 1. Units and vocabulary

| Term | Definition |
|---|---|
| **Provider** | A company or product, e.g. E2B or Daytona. |
| **Configuration** | **The unit we rank.** It is a provider, sandbox type, plan, region and size, e.g. `daytona/container/tier1/us/2c4g`. Daytona containers and Daytona Linux VMs are different products with different features, so they are separate configurations. |
| **Track** | A family of related benchmarks with its own leaderboard, e.g. `lifecycle`, `state`, `workloads`, `scale`, `gpu`, `browser`, `cost`, `capabilities`. |
| **Benchmark** | One measured scenario inside a track, e.g. `state/pause-resume`. It declares the capabilities it requires. |
| **Metric** | One number a benchmark produces, e.g. `resume_ready_ms` or `memory_preserved`. |
| **Sample** | One measurement of one metric in one iteration. |
| **Run** | One execution of a set of benchmarks against a set of configurations. It has a `run_id` and a manifest. |
| **Division** | `default` (stock SDK, documented defaults, publicly available plan), `optimized` (any documented feature or plan, disclosed) or `submitted` (vendor-run, see [GOVERNANCE §7](GOVERNANCE.md#7-vendor-submitted-results)). Divisions are never mixed in one ranking. |
| **Harness version** | A semver tag of this repo. A **major** bump means numbers are not comparable across versions. |

## 2. Standard sandbox spec

The aim is to compare like with like and to allow no hidden tuning.

- **Size:** 2 vCPU / 4 GiB RAM / ≥10 GiB disk. Where a provider has fixed shapes, we use the nearest shape at or above it and record the actual shape. Example: Cloudflare `standard-3` is 2 vCPU / 8 GiB.
- **Images:** two modes, each reported separately.
  - `default-image`: the provider's default or base image. This is what a new user experiences first.
  - `standard-image`: our public image `sandbox-bench/base:<version>`, built from a Dockerfile in this repo (Debian slim, Python 3.12, Node 22, git, build-essential). Each provider registers it as a template or snapshot ahead of time. Template build time is measured separately and excluded from start metrics.
- **Region:** the provider region closest to the runner, recorded per sample.
- **Network:** default egress settings.

## 3. Timing boundaries (the glossary that makes numbers comparable)

All timings are **client-side wall clock** taken with a monotonic clock (`time.perf_counter_ns`) in the harness, never from timings the provider reports. "Ready" always means **a command ran successfully inside the sandbox**, not "the API returned an ID".

| Metric | Clock starts | Clock stops |
|---|---|---|
| `create_ready_ms` (TTI) | Just before the SDK create call | The first `echo ready` exec returns exit code 0 with stdout `ready` |
| `exec_rtt_ms` | Before the exec call | Exec returns. We take the median of 20 sequential `true` execs on a ready sandbox. |
| `destroy_ms` | Before the destroy/kill call | The call returns successfully |
| `snapshot_ms` | Before the snapshot call | The snapshot is usable (ID returned and the status is ready where the SDK exposes status) |
| `restore_ready_ms` | Before the create-from-snapshot call | The first successful exec in the restored sandbox |
| `pause_ms` | Before the pause/suspend call | The call returns or the state becomes paused |
| `resume_ready_ms` | Before the resume call | The first successful exec in the resumed sandbox |
| `fork_ready_ms` | Before the fork/branch call | The first successful exec in the child, or in **all** N children for fan-out |
| `api_rtt_ms` | Before an HTTPS HEAD to the provider's API endpoint | Response received. This is network context only and is never subtracted. |

**Correctness metrics** for state operations. A fast operation that loses state does not count as success.

| Metric | How it is verified |
|---|---|
| `fs_preserved` | Before the operation, write a 64 MiB random file plus its SHA-256. Afterwards, re-hash it. |
| `memory_preserved` | Before the operation, start a background process holding a 256 MiB random buffer and a monotonic counter, and record its PID and buffer hash. Afterwards, the same PID must be alive, report the same hash, and its counter must continue from where it was. |
| `process_preserved` | The PID from the step above is still running. |
| `fork_isolation` | Child A writes a marker. The parent and child B must not see it. |

Each state benchmark reports latency **and** correctness. Latency counts toward a ranking only when the correctness check passes.

## 4. Benchmark catalog

The **v0.1** column marks the launch scope. Everything else is on the [roadmap](ROADMAP.md).

### Track `lifecycle`
| Benchmark | Metrics | v0.1 |
|---|---|---|
| `lifecycle/cold-start` | `create_ready_ms` (default-image and standard-image), `destroy_ms` | ✅ |
| `lifecycle/exec-latency` | `exec_rtt_ms`, plus `file_write_ms` and `file_read_ms` for 1 KiB and 10 MiB | ✅ |
| `lifecycle/template-build` | Time to register the standard image as a template | — |

### Track `state` (our headline differentiator)
| Benchmark | Metrics | v0.1 |
|---|---|---|
| `state/snapshot-restore` | `snapshot_ms`, `restore_ready_ms`, `fs_preserved`, `memory_preserved` | ✅ |
| `state/pause-resume` | `pause_ms`, `resume_ready_ms`, `fs_preserved`, `memory_preserved`, `process_preserved` | ✅ |
| `state/fork` | `fork_ready_ms` at fan-out 1 and 10, `memory_preserved`, `fork_isolation` | ✅ |
| `state/idle-autowake` | Time for a scale-to-zero sandbox to wake on request | — |

### Track `workloads` (real work inside the sandbox)
| Benchmark | Metrics |
|---|---|
| `workloads/repo-test` | Clone a pinned mid-size repo, install dependencies, run its test suite. Reports wall time and success. |
| `workloads/cpu` | A pinned compile job (e.g. building a fixed SQLite amalgamation) |
| `workloads/disk-io` | `fio` sequential and random read/write and a SQLite insert/query benchmark |
| `workloads/network` | Download throughput from a neutral CDN, and pip/npm install time |
| `workloads/terminal-bench` | **Harbor + Terminal-Bench 2.x oracle agent** at fixed concurrency. Reports pass rate, wall clock, environment-error rate, and cost per 100 tasks. Because the oracle solutions are correct, every failure is the sandbox's fault. |

### Track `scale`
| Benchmark | Metrics |
|---|---|
| `scale/burst` | N ∈ {10, 50, 100} concurrent creates. Reports success rate, `create_ready_ms` distribution, and rate-limit errors. **This is reported as capacity, never folded into latency rankings.** |
| `scale/sustained` | Creates per minute sustained for 10 minutes, and error rate |

### Track `capabilities` (the verified feature matrix)
Each capability is an executable **probe** with an outcome of `verified`, `claimed-but-failed`, `not-claimed` or `untested`. A `verified` badge needs the probe to pass in each of the last 3 runs.

Probes: custom OCI image · outbound internet · egress allowlist enforced · exposed port / preview URL · filesystem snapshot · memory snapshot · pause/resume · live fork · GPU (`nvidia-smi` + a CUDA matmul) · Docker-in-sandbox · headless Chromium launches · desktop/VNC · macOS · Windows · ARM64 · session length ≥ 1 h / 24 h (long-run probe, run occasionally).

### Later tracks
`gpu` (time to GPU ready, matmul throughput, $/GPU-hour), `browser` (time to Chromium ready, CDP page-load, computer-use desktop latency), `reliability` (error taxonomy over time, incident correlation), `dx` (time for a coding agent to reach a first working sandbox from the docs alone).

## 5. Measurement protocol

1. **Runner.** A fixed, dedicated VM in a declared region (v0.1: one US-East runner; v0.2: US-East, EU-West and AP-Southeast). Its spec, region and IP are recorded in each run manifest.
2. **Interleaving.** Iterations go round-robin across configurations, with the order **shuffled each round**. This spreads time-of-day and network effects evenly, instead of running all of provider A and then all of provider B.
3. **Iterations.** For latency, n = 30 measured iterations per configuration per run, plus 3 warm-up iterations. Warm-up iterations are recorded and flagged, never silently dropped. For state operations, n = 10 per run. Leaderboards aggregate a **rolling 7-day window**, which gives a few hundred samples per metric.
4. **Cadence.** v0.1 runs daily; v0.2 runs every 6 hours. Expensive workloads (Terminal-Bench) run weekly.
5. **Timeouts.** Create, restore, resume and fork time out at 120 s, and exec at 60 s. A timeout is a failure, never a sample capped at 120 s.
6. **Error attribution.**
   - **Provider errors** (5xx, timeouts, wrong results, rate limits on documented-normal usage) count as failures for the configuration.
   - **Harness errors** (our bug, our expired credentials, our exhausted credits) are excluded, logged, and shown in the run report.
   - The error taxonomy is stored with every failed sample.
7. **Cleanup.** Every sandbox is tagged `sandbox-bench/<run_id>`, and a reaper destroys leftovers after each run. Leaked sandboxes are reported.
8. **Accounts.** Each configuration runs on the provider's free-tier allowance or on credits the vendor has given the project. The credit source is recorded in the configuration metadata. Vendor-provided accounts are cross-checked periodically against a free-tier account ([GOVERNANCE §3](GOVERNANCE.md#3-accounts-and-credits)).

## 6. Statistics and presentation

- **Reported per metric:** n, success rate, p50, p90, p99 (p99 only when n ≥ 100), min and max, plus a bootstrap 95% CI for the median.
- **Success rate always appears next to latency,** in the same table cell or chart.
- **Charts:** ECDF or box plots by default, with an option to view all samples. A mean is never shown on its own.
- **Ranking.** Configurations are ordered by median. Configurations whose 95% CIs overlap share a **rank band** ("statistically tied"). This is the LMArena approach to ranks under uncertainty.
- **Freshness.** Every number shows the date of its window. Configurations with no successful run in 14 days are marked `stale`.

## 7. Cost

Cost is reported in two separate ways, and the two are never blended into one figure.

1. **List-price model.** `pricing/pricing.yaml` stores every rate with its source URL and the date it was checked. From it we compute:
   - `$/hour @ 2c4g, 100% CPU`, the worst case for CPU-bound work;
   - `$/hour @ 2c4g, 10% CPU`, a typical agent waiting on an LLM. This difference matters for providers that bill only active CPU (Vercel, Cloudflare, Sprites);
   - platform fees (monthly minimums), shown separately rather than amortized.
2. **Measured cost per task** (v0.2 onward). We run a workload, then read the provider's billing or usage API, or the invoice delta, and report `$ per 100 Terminal-Bench tasks` or `$ per 1000 cold starts`. Where usage can't be read back, the configuration is marked `estimated`.

Caveats are shown on the page, not hidden in footnotes: how a "core" is defined (vCPU vs physical core), fixed CPU:RAM ratios, per-creation fees, billing minimums, snapshot storage costs, and region multipliers.

## 8. Scores and rankings

- **Per-metric leaderboards** are the primary view.
- **Track score.** Within a track, each configuration gets the geometric mean over metrics of `(value + shift) / (best + shift)`, the ClickBench method. The shift is 10 ms for latency, which stops tiny absolute differences from producing huge ratios. Lower is better; 1.0 is the best on every metric.
- **Unsupported is N/A, not zero.** A configuration that doesn't claim a capability is left out of that track's ranking and shown as "not supported". One that claims a capability and fails the probe is ranked with a penalty: twice the worst value observed, the same as ClickBench's treatment of nulls.
- **Persona views.** These are named weightings of track scores with the weights visible, e.g. *Interactive coding agent*, *RL / eval rollouts*, *Long-lived stateful agent*. Users can adjust the weights in the UI. **There is no default "overall #1" on the home page.**

## 9. Versioning and change control

- Any change to a timing boundary, workload, standard image or scoring formula bumps the harness **minor** version (or **major** if it breaks comparability) and is recorded in `CHANGELOG.md` with its reason.
- SDK versions are pinned in a lockfile, and upgrades go through PRs. An SDK bump that moves a metric by more than 20% is called out in the run report.
- Methodology changes that affect rankings follow the RFC process in [GOVERNANCE.md](GOVERNANCE.md).
