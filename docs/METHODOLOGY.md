# Methodology

Everything about how sandbox-bench measures, on one page. If this page and the code disagree, the code wins, and the mismatch is a bug worth filing.

## 1. Setup

- **Sandbox size:** 2 vCPU / 4 GiB RAM. Where a provider has fixed shapes, we use the nearest one at or above this, and each row shows the actual size.
- **Environment:** the provider's default image and settings. A pre-started pool counts when the provider runs it for everyone at no extra cost; a warm pool billed while idle doesn't. Probes bring their own tools and need only `sh`, `sha256sum` and a writable `/dev/shm` inside the sandbox.
- **Runner:** one fixed machine in us-east. Each provider uses its region nearest the runner, shown in its row.
- **Accounts:** free tiers, or credits the provider gives the project.
- **Cadence:** one run per day, with 5 attempts per probe. Providers are interleaved in a shuffled order, with one operation in flight at a time. Each run starts with one uncounted warm-up create per provider.

## 2. Probes

A probe is a pass/fail check judged by a verifier. One **action** (for example "pause, then resume") can yield several probe verdicts, and each attempt also records its timings.

| Probe | Action | Passes when |
|---|---|---|
| `create-exec` | create a sandbox, run `echo` | The output is correct |
| `file-roundtrip` | write, then read a 10 MiB random file | The SHA-256 matches |
| `internet` | download a pinned file from a public CDN | The SHA-256 matches |
| `egress-block` | create with outbound traffic denied, try to connect out | The connection fails |
| `exposed-port` | start an HTTP server, call it via the provider's URL or port | It answers from the runner |
| `pause-keeps-files` | pause, then resume | The test file's hash matches |
| `pause-keeps-memory` | pause, then resume | The memory check (§3) passes |
| `snapshot-keeps-files` | snapshot, then create from it | The test file's hash matches |
| `snapshot-keeps-memory` | snapshot, then create from it | The memory check (§3) passes |
| `fork-keeps-memory` | fork once | The memory check (§3) passes in the child |
| `fork-isolation-x3` | fork three times, write a marker in one child | All 3 children run, and the marker is invisible to the parent and the other children |

**Outcomes:**
- **pass:** at least 9 of the last 10 attempts verified. Detail tables show the count, e.g. "9/10".
- **failing:** the provider offers the feature, but it passed fewer than 9 of the last 10 attempts.
- **n/a:** not offered, because the provider's public docs don't claim this behaviour.
- **pending:** fewer than 10 attempts so far.

**What counts as offered:**
- "Offered" is decided **per probe**. If the docs claim a snapshot keeps files but not memory, `snapshot-keeps-files` is offered and `snapshot-keeps-memory` is not.
- Each adapter lists its offered probes, each with a link to the docs that claim it.
- **Any public mechanism counts.** For example, a fork made by snapshotting and then creating copies passes the fork probes. The mechanism used is shown with the provider's results.

## 3. The memory check

Before the action, the harness starts a counter inside the sandbox: a plain `sh` loop that keeps `i` in memory and writes it to a file every 0.5 s. It also fills a 32 MiB buffer in `/dev/shm`, which lives in RAM. The harness then records:
- the loop's PID and process start time (`/proc/<pid>/stat`);
- its command line;
- the buffer's hash;
- the last counter value, `v0`.

After the action, the check passes only if all of these hold:
1. The same PID is running, with the same start time and command line.
2. The `/dev/shm` buffer has the same hash.
3. Two counter reads taken ≥ 2 s apart show `v0 ≤ r1 < r2`. The process is alive, continued from where it was, and is still counting. A process frozen while paused passes, because it resumes counting.

A restarted sandbox fails, because it has a new process start time and an empty `/dev/shm`. A stale counter file also fails, because the counter isn't rising.

## 4. Timings

All timings are client-side wall clock, taken by the harness around adapter calls. They never come from numbers the provider reports. **"Ready" always means a command succeeded inside the sandbox.**

| Metric | Clock starts | Clock stops | Column shown only if this passes |
|---|---|---|---|
| Start | before the create call | first `echo` succeeds | `create-exec` |
| Exec | before a `true` exec | it returns (median of 5 per attempt) | `create-exec` |
| Pause | before the pause call | the call returns | `pause-keeps-files` |
| Resume | before the resume call | first command succeeds | `pause-keeps-files` |
| Snapshot | before the snapshot call | the snapshot is usable | `snapshot-keeps-files` |
| Restore | before create-from-snapshot | first command succeeds | `snapshot-keeps-files` |
| Fork | before the fork call (including any snapshot step) | first command succeeds in the child | `fork-keeps-memory` |
| API RTT | before a trivial authenticated API call | it returns | none (context only) |

**Which attempts become samples:**
- the attempt succeeded;
- it used a default create, so probes created with egress denied never feed Start;
- it carried the same payload as every other provider's attempts.

**Timeouts** are per operation and the same for every provider:

| Operation | Timeout |
|---|---|
| create, restore, resume, fork | 120 s |
| exec | 60 s |
| snapshot | 15 min |

A timeout is a failure, never a capped sample. Any rate-limit pacing happens outside the clock.

**Start mode** (pool, memory or cold) is declared by the adapter. At the first exec, the harness also records `/proc/uptime` and the boot ID as evidence.

## 5. Scoring and ranking

- **Main table:**
  - Rows are ranked by the number of probes passed, with ties broken by Start p50.
  - There are no weights and no percentages.
- **Speed columns:**
  - Each shows the median (p50) of the last 10 attempts. Fork is the time to the first command in one fork.
  - A provider appears in a column only if it passes that column's probe.
  - A column with fewer than 10 samples is shown but not ranked.
- **Keeps memory on** lists pause, snapshot and fork when the matching memory probe passes. A files-only resume can't be mistaken for a full one.
- **State columns** (Resume, Restore, Fork) rank only sandboxes at the standard 2 vCPU / 4 GiB. Memory size changes these timings.
- **Per-metric tables** add p90, n, success rate, the date window, plan, size, region and API RTT.
- **Per-provider facts:** each provider gets a plain line generated from data, for example "Pause: not offered. Snapshot: files only, 368 s."
- **Errors:**
  - Provider errors (5xx responses, timeouts, wrong results) count as failures.
  - Our own errors (a harness bug, an expired key, exhausted credits, an account limit) are excluded and listed in the run log.
  - Every failing probe links to its error, the verifier's evidence and the `sbx check` command that reproduces it.

## 6. Cost

Prices come from `pricing/pricing.yaml`, where each rate has its source link and the date it was checked.

- **$/h running:** list price for one 2 vCPU / 4 GiB sandbox running for an hour.
- **$/h paused:** list price for keeping that sandbox paused for an hour (storage and any fees). It is n/a when pause isn't offered.

Per-creation fees, billing minimums and monthly platform fees are shown with the provider's results.

## 7. Cleanup

- Every resource the harness creates is named `sbx-<run_id>-…`.
- A reaper deletes leftovers matching that prefix before and after every run.
- It never touches anything else on the account.

## 8. Versioning

The benchmark has one version, starting at `v0.1`. Adding or changing a probe, a clock boundary or the scoring bumps it, after a 7-day notice in an issue. Scores are compared only within one version. SDK versions are pinned, and upgrades go through PRs.
