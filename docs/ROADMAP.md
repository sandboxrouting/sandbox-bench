# Roadmap

**v0.1** has two parts:
1. One maintainer builds the foundation and proves it on two real providers.
2. Both maintainers then add one provider per PR, every day, until launch.

## 1. Foundation

| PR | What | Done when |
|---|---|---|
| F1 | Skeleton: `uv` project, CI (`ruff` + `pytest`), the `Adapter` interface, result schema, fake provider | CI is green; the fake provider loads |
| F2 | Engine: runner (shuffled order, one operation in flight), timing, per-operation timeouts, pacing, cleanup by name prefix | `sbx run --providers fake` writes valid results |
| F3 | The 11 probes as 5 actions (basics, network, pause, snapshot, fork), each tested pass and fail on the fake provider | Every probe has a passing and a failing test |
| F4 | **Daytona** (SDK) and **Freestyle** (REST) adapters | Both run every probe live; the memory probes pass on Freestyle |
| F5 | `sbx check`, `providers/_template.py`, `sbx report` writing Markdown tables and `results.json` | A new adapter can be checked without reading harness code |
| F6 | The fixed machine: a daily cron job that pushes raw results to a separate results repo | Daytona and Freestyle have run daily for several days |

## 2. Provider sprint

One provider per PR, split between the two maintainers. Planned: E2B, Modal, Vercel, Blaxel, Tensorlake, Morph, and Orble if it has an API we can call.

**A provider PR is done when:**
- the adapter file is complete and lists every offered probe with a docs link;
- `sbx check` passes, with its table in the PR;
- the provider's terms allow publishing benchmark results;
- the account runs 2 vCPU / 4 GiB on a public plan (free tier, credits or pay-as-you-go), named in its row ([ADR-0006](decisions/0006-paid-plans-allowed.md)).

## 3. Launch

- Every launched provider has 10 attempts per probe.
- Each provider gets its results 7 days before launch and can add a note.
- The launch post leads with the memory probes, e.g. "We paused N sandboxes 1,000 times. Here's which ones kept your process."
- The post may compare published claims with our numbers. It cites each claim's source and stated clock boundary, names the runner region, and never calls a claim false.
- Open 10 or more `good-first-issue`s, plus a "propose a probe for your best feature" issue template.

## After v0.1

| Next | Contents |
|---|---|
| **v0.2** | <ul><li>Probes: `docker-in-sandbox`, `dockerfile`, `pause-1h-resume`</li><li>A pinned toolset (Python, Node, build tools) and a "Start with toolset" column</li><li>A claim column: each provider's published number with its source and clock boundary</li><li>Embeddable badges</li><li>Cloudflare, via a TypeScript bridge</li></ul> |
| **v0.3** | <ul><li>Specialized probes: Chromium via CDP, desktop screenshot, GPU, ARM64, macOS, Windows</li><li>More runner regions</li></ul> |
| **Later** | <ul><li>Website</li><li>Real workloads (Terminal-Bench via Harbor)</li><li>Burst and scale tests</li><li>Measured (billed) cost</li><li>A weekly "what changed" post</li><li>An agent-readable feed of results</li></ul> |

## Risks

| Risk | What we do |
|---|---|
| A provider disputes a result | Public verifiers and evidence, a reproduce command on every failing probe, provider notes |
| Adapters rot as SDKs change | Pinned SDKs, an owner per adapter, the 14-day stale rule |
| Free credits run out | Small payloads, few attempts per day, credits requested early |
| Scope creep | A ~1,500-line budget for the harness, and one version for everything |
