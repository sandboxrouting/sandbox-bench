# Roadmap and action plan

**Strategy:** launch quickly with something small that nobody else offers, then widen coverage based on what people ask for.

The launch wedge is **"lifecycle + state"**, made up of:

- cold-start numbers, taken through native SDKs;
- **the first independent check of whether snapshot, pause/resume and fork really keep memory and processes, and how fast they are.**

These are the most heavily marketed claims in the sandbox market, and no one has verified them. That is a launch story people will want to share.

---

## v0.1 "Launch" (about 4 weeks of part-time work)

**Scope:**
- Tracks `lifecycle` and `state`.
- A partial `capabilities` matrix (the probes that fall out of these tracks).
- A list-price `cost` table.
- One runner region and daily runs.
- A static site and raw data in git.

**Launch providers:** E2B, Daytona (container, plus Linux VM if accessible), Modal, Vercel Sandbox, Blaxel, Tensorlake and Morph. All seven have Python SDKs. Each joins once its free tier or donated credits can run the standard 2 vCPU / 4 GiB size (Tensorlake's free tier, for example, needs credits). Freestyle and Cloudflare join in v0.2 through the TypeScript bridge.

**Harness:** Python 3.12 with `uv` (see [ARCHITECTURE](ARCHITECTURE.md#stack)).

**Accounts and credits:** every provider runs on its free-tier allowance or on credits the vendor gives the project. Each configuration notes its credit source (see [GOVERNANCE](GOVERNANCE.md#accounts-and-credits)).

### Week 0: foundations (2–3 days)
- [ ] Create provider accounts, claim free-tier credits, and ask each launch vendor for benchmark credits.
- [ ] Check each provider's ToS for benchmark-publication clauses ([GOVERNANCE](GOVERNANCE.md#terms-of-service)). Record the findings.
- [ ] Repo hygiene:
  - [ ] `CODE_OF_CONDUCT.md`, `SECURITY.md`, and `MAINTAINERS.md`.
  - [ ] Issue templates: `new-provider`, `new-benchmark`, `dispute`, `bug`.
  - [ ] PR template, and a `ruff` + `pytest` CI.
- [ ] Turn on GitHub Discussions, and open "Ideas for benchmarks" and "Provider requests" threads.

### Week 1: harness core and the first 3 adapters
- [ ] `schema.py`: result models and manifest. Export JSON Schema.
- [ ] `adapter.py`: the protocol, the `Capability` enum and `provider.yaml` loading.
- [ ] `timing.py` and `runner.py`: interleaved, shuffled round-robin; timeouts; error attribution; warm-up flagging.
- [ ] `reaper.py`: tag-based cleanup.
- [ ] A mock adapter and unit tests for the runner and stats.
- [ ] Adapters for **E2B, Modal and Daytona**.
- [ ] Benchmarks `lifecycle/cold-start` and `lifecycle/exec-latency`.
- [ ] `sbx run --providers e2b,modal --bench lifecycle/* --n 5` works locally.

### Week 2: state track and the remaining providers
- [ ] `checks.py`: the file-hash check, the memory-holder process (256 MiB buffer + counter + PID) and the fork-isolation marker.
- [ ] Benchmarks `state/snapshot-restore`, `state/pause-resume` and `state/fork`.
- [ ] Adapters for **Vercel, Blaxel, Tensorlake and Morph**. Add Daytona Linux VM if it is accessible.
- [ ] Build and publish the standard image, and register it as a template on each provider.
- [ ] Fill in `pricing/pricing.yaml` with sources and the date checked.

### Week 3: automation, statistics and site
- [ ] Provision the runner VM in us-east-1 as an ephemeral self-hosted runner. Add the scheduled workflow (daily) and the results PR bot with schema validation.
- [ ] `stats.py`: percentiles, bootstrap CI and rank bands over a 7-day rolling window.
- [ ] Site pages:
  - [ ] **Home:** what the project is, its principles, latest run date.
  - [ ] **Per-track leaderboards** with ECDF charts and success rates.
  - [ ] **Capability matrix** showing verified / claimed-but-failed / N/A.
  - [ ] **Provider profile:** configurations, distributions, history sparkline, vendor note, raw-data links.
  - [ ] **Methodology,** rendered from `docs/`.
  - [ ] **Compare A vs B.**
- [ ] Collect at least 7 days of data before launch, so the first public numbers are a window and not a single run.

### Week 4: vendor preview and launch
- [ ] Send the 7-day preview to every included vendor ([GOVERNANCE](GOVERNANCE.md#working-with-providers)) and invite vendor notes and adapter reviews.
- [ ] Fix any adapter issues providers raise.
- [ ] Write the launch post. Lead with the state-ops findings, e.g. "We paused 8 sandboxes 1,000 times. Here's which ones kept your memory." Include methodology and limitations up front.
- [ ] Launch: Show HN, X/LinkedIn, r/LocalLLaMA and agent-builder communities. Tag vendors respectfully.
- [ ] Publish `CONTRIBUTING.md` paths for "add a provider" and "add a benchmark", plus 10 or more `good-first-issue`s, such as new probes, a new provider adapter, or a chart improvement.

### v0.1 cost estimate (to be confirmed in week 2)
- A cold-start iteration keeps a sandbox alive for about 10 s. 33 iterations come to roughly $0.02 per configuration.
- State benchmarks run 10 iterations at about 60 s each, roughly $0.03–0.10 per configuration.
- Billing minimums can multiply this by 2–5×.
- **Total: about 8 configurations × daily × 30 days ≈ $10–50/month, plus the runner VM at ~$10–15/month.** This is covered by free-tier allowances and vendor-given credits.

### Launch success signals (review at launch + 30 days)
- Vendor engagement: replies, adapter PRs and notes.
- External citations.
- Stars and watchers as a weak signal.
- The number of benchmark ideas and provider requests that come in.
- Whether anyone reproduces a result independently.

---

## After launch

| Release | Theme | Contents |
|---|---|---|
| **v0.2** (launch + 4–6 weeks) | Workloads, scale and regions | <ul><li>`workloads/terminal-bench`: a Harbor oracle run, weekly, at fixed concurrency</li><li>`workloads/repo-test`, `cpu`, `disk-io` and `network`</li><li>`scale/burst` reported as capacity</li><li>Three runner regions and a 6-hour cadence</li><li>Persona views on the site</li><li>The TypeScript bridge, which brings in Freestyle and Cloudflare</li><li>`default` vs `optimized` divisions</li></ul> |
| **v0.3** | Measured cost and reliability | <ul><li>Billing-API reconciliation, giving `$ per 100 tasks`</li><li>An error taxonomy dashboard</li><li><strong>Vendor-submitted results:</strong> vendors run the harness on their own accounts and submit the output, published in a separate <code>submitted</code> division (see <a href="GOVERNANCE.md#submitted-results-planned">GOVERNANCE</a>)</li><li>Regression alerts that open an issue and ping the vendor when a metric gets more than 20% worse</li><li>A public results API (static JSON)</li></ul> |
| **v0.4** | Specialized environments | <ul><li>`gpu` track: time to GPU ready, matmul throughput, $/GPU-hour</li><li>`browser` track: Chromium ready, CDP page loads, desktop/VNC latency</li><li>macOS/Windows probes</li><li>Docker-in-sandbox</li><li>Scale-to-zero auto-wake</li></ul> |
| **v0.5** | Security and networking (non-destructive) | <ul><li>Egress allowlist enforcement</li><li>Secret-injection behavior</li><li>Exposed-port and preview-URL latency</li><li>Isolation *documentation* checks (no attack testing)</li></ul> |
| **v1.0** | Governance maturity | <ul><li>A steering group (maintainers plus a rotating community seat; vendors advise without voting)</li><li>RFC process in active use</li><li>Verified badges providers can embed</li><li>Yearly "State of Agent Sandboxes" report</li><li>An evaluation of fiscal hosting (e.g. OpenCollective or a foundation)</li></ul> |
| **Later / research** | New ideas | <ul><li>A `dx` track: a coding agent onboards from the docs alone</li><li>Opt-in "observed in production" telemetry</li><li>BYOC / self-hosted track</li><li>Long-session (24 h+) soak tests</li><li>A sandbox recommendation wizard driven by persona weights</li></ul> |

## Risks and mitigations

| Risk | Mitigation |
|---|---|
| Providers disagree with results | Native SDKs, public data, provider notes, and issues worked out in public |
| Vendor ToS forbids publishing results | ToS check before inclusion; ask for permission in writing and publish the exchange |
| Costs grow with tracks and regions | Budget guard, vendor-given credits, vendor-submitted results for expensive tracks, and weekly cadence for expensive workloads |
| Maintainer burnout (the TechEmpower lesson) | Small scope, automate everything, vendors maintain their own adapters, and an explicit "not now" list |
| SDK churn breaks adapters | Pinned SDKs, Renovate PRs, and a daily canary that opens an issue on adapter failure |
| Numbers go stale or providers pivot | Every number dated, `stale` flag after 14 days, configurations deprecated publicly |
