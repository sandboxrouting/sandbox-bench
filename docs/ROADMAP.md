# Roadmap and action plan

**Strategy:** launch quickly with something small that nobody else offers, then widen coverage based on what people ask for.

The launch has two parts:

- **Probe suite `core-v0.1`** (15 probes across lifecycle, state and environment). It answers "what can each sandbox actually do?" Its centrepiece is the first independent check of whether snapshot, pause/resume and fork really keep memory and processes.
- **Performance boards** for start, start with toolset, exec, file I/O, snapshot/restore, pause/resume, fork and cost. They answer "how fast and how cheap is it?"

The launch story writes itself: a ranked table where every ✓ was earned, and speed races that only count features that actually work.

---

## v0.1 "Launch" (about 4 weeks of part-time work)

**Scope:**
- Probe suite `core-v0.1` and the v0.1 performance boards ([METHODOLOGY §4–5](METHODOLOGY.md#4-probe-suite-core-v01)).
- The main leaderboard ranked by probe score.
- List-price cost.
- Daily runs.
- A static site and raw data in git.

**Launch providers:**
- E2B, Daytona (container, plus Linux VM if accessible), Modal, Vercel Sandbox, Blaxel, Tensorlake and Morph. All seven have Python SDKs.
- Each joins once its free tier or donated credits can run 2 vCPU / 4 GiB. Tensorlake's free tier, for example, needs credits.
- Freestyle and Cloudflare join in v0.2 through the TypeScript bridge.

**Harness:** Python 3.12 with `uv`, and `sbx-helper` in Go (see [ARCHITECTURE](ARCHITECTURE.md#stack)).

**Accounts and credits:** every provider runs on its free-tier allowance or on credits the provider gives the project ([GOVERNANCE](GOVERNANCE.md#accounts-and-credits)).

### Week 0: foundations (2–3 days)
- [ ] Create provider accounts, claim free-tier credits, and ask each launch provider for benchmark credits.
- [ ] Check each provider's ToS for benchmark-publication clauses ([GOVERNANCE](GOVERNANCE.md#terms-of-service)).
- [ ] Repo hygiene:
  - [ ] `CODE_OF_CONDUCT.md`, `SECURITY.md` and `MAINTAINERS.md`.
  - [ ] Issue templates: `new-provider`, `new-probe`, `dispute`, `bug`.
  - [ ] PR template, and a `ruff` + `pytest` CI.
- [ ] Turn on GitHub Discussions, with "Probe ideas" and "Provider requests" threads.

### Week 1: harness core, lifecycle, first 3 adapters
- [ ] `schema.py`: probe attempts, metric samples and the run manifest. Export JSON Schema.
- [ ] `adapter.py`: the protocols, `NotSupported`, and `provider.yaml` loading.
- [ ] `timing.py` and `runner.py`:
  - [ ] interleaved, shuffled round-robin with one operation in flight;
  - [ ] timeouts, error attribution and warm-up flagging;
  - [ ] start-mode detection.
- [ ] `reaper.py`: tag-based cleanup.
- [ ] A mock adapter, and unit tests for the runner and scoring.
- [ ] `toolset/v1.yaml`, `toolset/Dockerfile` and `toolset/setup.sh`.
- [ ] Adapters for **E2B, Modal and Daytona**.
- [ ] Lifecycle probes: `create-exec`, `file-roundtrip` and `toolset`.
- [ ] Boards: Start, Start with toolset, Exec round-trip and File I/O.
- [ ] `sbx run --providers e2b,modal --n 5` works locally.

### Week 2: helper, state and environment probes, remaining providers
- [ ] `sbx-helper` (Go, static, amd64 and arm64): `hold`, `inspect`, `mark`/`check`, `toolset-check` and `start-age`.
- [ ] State probes: `snapshot-keeps-files/memory`, `pause-keeps-files/memory`, `fork-keeps-memory` and `fork-isolation-x10`.
- [ ] Environment probes: `dockerfile`, `internet`, `egress-block`, `exposed-port` and `docker-in-sandbox`.
- [ ] `session-1h`, scheduled weekly.
- [ ] Boards: Snapshot & restore, Pause & resume, and Fork, each with a memory column.
- [ ] Adapters for **Vercel, Blaxel, Tensorlake and Morph**, plus Daytona Linux VM if accessible.
- [ ] `pricing/pricing.yaml` with sources and the date each rate was checked. Cost board.

### Week 3: automation, scoring and site
- [ ] Set up the publishing runner: a fixed machine in a declared region, the daily scheduled workflow, and a results PR bot with schema validation.
- [ ] `scoring.py`: probe pass rates over the 7-day window, category means and the probe score.
- [ ] `stats.py`: percentiles, bootstrap CI and rank bands.
- [ ] Site pages:
  - [ ] **Main leaderboard:** ranked by probe score, with headline board columns and sortable columns.
  - [ ] **Probe matrix:** configurations × probes, showing ✓ / ✗ / — with success rates.
  - [ ] **Board pages:** rank bands, ECDF charts, start-mode and memory columns, and a "memory kept only" filter.
  - [ ] **Provider pages:** configurations, history, provider note and raw-data links.
  - [ ] **Methodology,** rendered from `docs/`.
  - [ ] **Compare A vs B.**
- [ ] Collect at least 7 days of data before launch.

### Week 4: provider preview and launch
- [ ] Send the 7-day preview to every included provider ([GOVERNANCE](GOVERNANCE.md#working-with-providers)). Invite provider notes and adapter reviews.
- [ ] Fix any adapter issues providers raise.
- [ ] Write the launch post. Lead with the leaderboard and the state probes, e.g. "We paused 8 sandboxes 1,000 times. Here's which ones kept your memory."
- [ ] Launch: Show HN, X/LinkedIn and agent-builder communities. Tag providers.
- [ ] Open 10 or more `good-first-issue`s: new probes, new adapters, chart improvements.

### v0.1 cost estimate (to be confirmed in week 2)
- **Speed boards:** about 33 short-lived sandboxes per board per configuration, roughly $0.02–0.05.
- **State boards and probes:** about 60 s per iteration, roughly $0.05–0.15 per configuration.
- **`session-1h`:** weekly, about $0.17 per configuration.
- **Billing minimums** can multiply these by 2–5×.
- **Total:** about 8 configurations × daily × 30 days ≈ **$15–60/month**, covered by free tiers and donated credits.

### Launch success signals (review at launch + 30 days)
- Provider engagement: replies, adapter PRs and notes.
- External citations of the leaderboard.
- Probe ideas and provider requests coming in.
- Anyone reproducing a result independently.
- Stars and watchers, as a weak signal.

---

## After launch

| Release | Theme | Contents |
|---|---|---|
| **v0.2** | More providers and boards | <ul><li>The TypeScript bridge, which brings in Freestyle and Cloudflare</li><li><code>scale</code> boards: burst at N = 10/50/100 and sustained creates per minute</li><li><code>workloads</code> boards: repo clone/install/test, CPU, disk and network, each with pinned binaries</li><li>Three runner regions and a 6-hour cadence</li><li>The <code>optimized</code> division</li></ul> |
| **v0.3** | Specialized probes | <ul><li>Suite <code>core-v0.2</code> with a <code>specialized</code> category: <code>chromium-cdp</code>, <code>desktop-screenshot</code>, <code>gpu-matmul</code>, <code>arm64</code>, <code>macos</code>, <code>windows</code></li><li>Matching boards: time to Chromium ready, GPU ready and $/GPU-hour</li></ul> |
| **v0.4** | Real workloads and measured cost | <ul><li>Terminal-Bench via Harbor (oracle agent, weekly): pass rate, wall clock, cost per 100 tasks</li><li>Billing-API reconciliation</li><li><strong>Submitted results</strong> (<code>sbx submit</code>, the <code>submitted</code> division, see <a href="GOVERNANCE.md#submitted-results-planned">GOVERNANCE</a>)</li><li>Regression alerts to providers</li><li>A public results API (static JSON)</li></ul> |
| **v0.5** | Networking and security (non-destructive) | <ul><li>Egress allowlist probes</li><li>Secret injection</li><li>Preview-URL latency</li><li>Idle auto-wake</li><li>Resume after 24 h</li></ul> |
| **v1.0** | Maturity | <ul><li>A steering group with a rotating community seat</li><li>Verified badges providers can embed</li><li>A yearly "State of Agent Sandboxes" report</li><li>An evaluation of fiscal hosting</li></ul> |
| **Later** | New ideas | <ul><li>A <code>dx</code> board: a coding agent onboards from the docs alone</li><li>Opt-in production telemetry</li><li>A BYOC / self-hosted track</li><li>Soak tests over 24 h</li></ul> |

## Risks and mitigations

| Risk | Mitigation |
|---|---|
| Providers disagree with results | Native SDKs, public verifiers and raw data, provider notes, and issues worked out in public |
| One category dominates the score | Probe score is the mean of category pass rates; new categories need an RFC |
| Probes become stale or too easy | Versioned suites; the community proposes harder probes for each new suite version |
| Vendor ToS forbids publishing results | ToS check before inclusion; ask for permission in writing and publish the exchange |
| Costs grow with boards and regions | Budget guard, donated credits, submitted results for expensive boards, weekly cadence for expensive probes |
| Maintainer burnout (the TechEmpower lesson) | Small scope, automate everything, providers maintain their own adapters |
| SDK churn breaks adapters | Pinned SDKs, Renovate PRs, and a daily canary that opens an issue on adapter failure |
