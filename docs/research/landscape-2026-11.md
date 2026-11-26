# Landscape research: November 2026

> Snapshot taken **2026-11-24**. This market changes month to month, so treat every number here as dated.
> Vendor claims are marked *claimed*. Things we could not confirm are marked *unverified*.
> Background for the [README](../../README.md) and the [methodology](../METHODOLOGY.md).

## 1. Existing sandbox benchmarks and comparisons

| Source | Run by (conflict of interest) | What it measures | Methodology quality | Main gaps |
|---|---|---|---|---|
| [ComputeSDK Benchmarks](https://www.computesdk.com/benchmarks/sandboxes) ([code](https://github.com/computesdk/benchmarks)) | ComputeSDK. It sells a "Sandbox Router" and paid sponsorship tiers (logo in tables, "claimed profile", early data access, advisory seat). It sells private "Stealth" benchmarks for $3k/mo per category, and some sponsors also appear in the rankings. | Burst TTI: 100 concurrent `create()` until `node -v` succeeds. Also a DAX workload (clone + `bun install` + typecheck) and reliability. About 37 providers. | Open harness, weekly cron, p50/p95/p99 and success rate. | All calls go through ComputeSDK's own abstraction, not native SDKs. One undisclosed region. The composite score squashes differences (100 ms vs 1 s comes out as about 99 vs 90). Success rate is mixed into a latency score. No run date on the page. Raw data is not in the repo. No snapshot, fork, resume, cost or feature coverage. |
| [Lizard: E2B vs Daytona vs Modal](https://lizard.build/blog/e2b-vs-daytona-vs-modal) | Lizard, a sandbox vendor (disclosed) | Create latency, 300 starts per provider after 3 warm-up rounds, pinned SDKs, one client (us-east4) | **Best methodology we found:** full percentiles, raw CSV and script published | Covers 4 providers, the vendor ranks itself first, and it is a one-off post. |
| [Tensorlake sandbox-sqlite-bench](https://github.com/tensorlakeai/sandbox-sqlite-bench) | Tensorlake (vendor) | Filesystem I/O at 2 vCPU / 4 GB | n=3, mean ± sd | Run by a vendor, regions unstated. |
| [Tensorlake: Accelerating Harbor](https://tensorlake.ai/blog/accelerating-harbor-with-tensorlake) | Tensorlake (vendor) | Terminal-Bench 2 oracle runs on Harbor: Tensorlake 89/89 in 37 min, Modal 86/89, Daytona 56/89 with 26 start timeouts | A real workload, but run once by a vendor | No concurrency or repeat data. **Shows that a real-workload metric gets attention.** |
| [Beam benchmarks](https://www.beam.cloud/benchmarks) | Beam (vendor) | Its own cold start, image pull, volume I/O | Often a single run, sometimes from a laptop | Mostly measures itself only. |
| [LogRocket comparison](https://blog.logrocket.com/comparing-ai-agent-sandbox-platforms-e2b-modal-daytona-and-more/) | Editorial | Create and resume to first command | Iterations, region and code not stated | Points out that **"resume" means different things on different providers**. |
| [Superagent "benchmark"](https://www.superagent.sh/blog/ai-code-sandbox-benchmark-2026) | Editorial | Repeats vendor claims (Blaxel 25 ms, Daytona 90 ms, E2B 150 ms) | No measurement | These numbers are widely re-quoted as if they were benchmark results. |
| [Firegoat Agent Arena](https://firegoat.ai/arena/sandboxes) | Firegoat (sells a paid "report to improve your rank") | A coding agent onboards itself onto each provider and is scored on time, cost and errors | New idea (DX for agents), but no code and no date | Pay-to-improve conflict. |
| [nibzard/ai-sandbox-benchmark](https://github.com/nibzard/ai-sandbox-benchmark) | Possibly Daytona-origin (*unverified*) | TUI covering 5 providers | Proof of concept | Treats Daytona specially and has no leaderboard. |
| Vendor "X vs Y" pages (Fly.io, Upstash, Modal, Northflank, Morph, Blaxel…) | The vendors themselves | Feature matrices | Marketing | Each names itself "best overall". |

Feature lists: [awesome-ai-sandboxes](https://github.com/tizkovatereza/awesome-ai-sandboxes), [awesome-sandbox](https://github.com/restyler/awesome-sandbox), [awesome-agent-sandbox](https://github.com/fishman/awesome-agent-sandbox).

### Key takeaways
1. **No neutral benchmark exists.** Every serious one is run by a vendor, a router or a seller of paid reports.
2. Almost everything measures **create latency only**. Nobody independently checks state operations: snapshot, restore, pause/resume with **memory preservation**, and live fork. Yet these are the most marketed and least verified claims.
3. Nobody publishes a **feature matrix checked by executable tests**. Every matrix is copied from docs.
4. Nobody measures **cost per task** from real metering.
5. Burst-concurrency figures get read as latency. One critique ([bex.co](https://bex.co/blog/2026/10/04/superagent-sandbox-benchmark-cold-start-concurrency)) points out that a median from a run with 37% success describes capacity, not latency.

### Vendor claims to verify independently

| Provider | Claim | What independent measurements found |
|---|---|---|
| Daytona | "sub-90 ms creation" | 483–819 ms |
| E2B | "~150 ms" start | 264–1041 ms |
| Blaxel | "<25 ms resume from standby" | Unverified. The standby trigger is described inconsistently. |
| Morph | Snapshot/branch/restore "<250 ms" | Unverified |
| Freestyle | Fork "<50 ms", boot "<800 ms" | Unverified |
| Modal | About 1 s memory-snapshot restore | That figure is for Functions. There is no figure for Sandboxes. |
| Fly Sprites | Warm wake 100–500 ms, checkpoint about 300 ms | Unverified |
| Runloop | "<2 s for a 10 GB image" | Unverified |

## 2. Precedents from other benchmarks (patterns we adopt)

| Precedent | What we copy | What we avoid |
|---|---|---|
| **[Harbor](https://docs.harborframework.com) + [Terminal-Bench](https://www.tbench.ai)** | A task directory format (`instruction`, `environment/`, `solution/` as the oracle, `tests/` as the verifier). A provider adapter interface (`start/stop/exec/upload/download`) with a **declared capabilities object**. Versioned datasets. Harbor already ships about 37 sandbox provider integrations, **so Terminal-Bench oracle runs can serve as a real-world workload metric** (every failure is the sandbox's fault). | The [leaderboard gaming incidents](https://www.tbench.ai/news/leaderboard-integrity-update) (changed timeouts, leaked solutions), which is why submitters must not control the harness. |
| **[ClickBench](https://github.com/ClickHouse/ClickBench)** | One directory per system. Results as JSON committed to git. A static site generated from that data. Tuned results labelled and listed separately. `null` for missing results. Score = geometric mean of `(t+shift)/(best+shift)`. Tags so readers compare like-for-like. | Results that are vendor-run and tuned toward the benchmark. A single flat workload. |
| **[Artificial Analysis](https://artificialanalysis.ai/methodology/performance-benchmarking)** (benchmarks LLM *providers*, the closest analog to us) | Scheduled probes (every 6 h). A rolling window of medians. **"Mystery shopper" anonymous accounts** to cross-check accounts the provider supplied. Provider-side errors count against the provider and harness-side errors are excluded. A published **sanctions ladder** for non-representative serving. | A paid enterprise tier, which looks pay-to-play. Disclosed reliance on a single region. |
| **[MLPerf](https://github.com/mlcommons/policies/blob/master/submission_rules.adoc)** | A **Closed vs Open** division (stock config vs anything-goes but disclosed). **Available vs Preview** tags. A peer-review objection window. A **results-citation policy** for vendor marketing. | A heavy process and pay-to-join membership. |
| **[SWE-bench](https://github.com/SWE-bench/experiments)** | Submissions as metadata files in git, plus a CLI for packaging and verification. | |
| **[TechEmpower](https://github.com/TechEmpower/FrameworkBenchmarks)** | Precise per-test rules, and a "Stripped" label for implementations that cut corners. | **Vendor-written implementations led to endless optimization disputes, and the repo was archived in March 2026 after maintainer burnout.** So maintainers own the harness, adapters stay thin, and maintainer load needs a budget. |
| **[Shilkov cold-start research](https://mikhail.io/serverless/coldstarts/methodology/)** | Client-side end-to-end timing. Coldness detected rather than guessed. Distributions instead of averages. Results dated because they go stale. | |
| **[OpenRouter](https://openrouter.ai/docs/features/provider-routing)** | Later on: opt-in "observed in production" telemetry alongside our synthetic probes. | |

## 3. Provider landscape (feature snapshot)

**Structural facts that affect the design:**
- **ComputeSDK is not a provider.** It is an MIT-licensed abstraction and router over E2B, Modal, Daytona, Vercel and others. It also runs the most visible competing benchmark. We list it under "related projects", not as a provider.
- **Daytona went closed source** in June 2026. It has *several sandbox types* (container, Linux VM, Windows VM, macOS) with different feature sets: containers can't fork or take memory snapshots. **So each row is a provider *and product*, e.g. "Daytona (container)", not just a provider.**
- **Runloop may be winding down** (*unverified*: one third-party source cites end of support on 2026-11-13). Confirm before integrating.
- **CodeSandbox SDK is legacy.** It is being replaced by Together's `together-sandbox`, which is sales-gated.
- New entrants in 2026: AWS Lambda MicroVMs, Baseten Sandboxes, Upstash Box, Google Agent Compute Engine (preview), GKE Agent Sandbox, DigitalOcean Managed Agents (preview), Novita.

| Provider | Isolation | Memory snapshot / pause | Live fork | GPU | macOS / Windows | Desktop / computer use | ≈ $/h at 2 vCPU / 4 GB* |
|---|---|---|---|---|---|---|---|
| E2B | Firecracker (OSS) | Yes | Yes | No | No | Yes | 0.166 |
| Daytona (container) | Container | Filesystem only | No | Yes | — | — | 0.166 |
| Daytona (VM types) | VM | Yes | Yes | ? | **Yes, both** | Yes | ? |
| Modal | gVisor (VM alpha) | Alpha | No | **Yes (T4–B300)** | No | No | 0.24–0.38 |
| Tensorlake | Firecracker | Yes | Yes | ? | No | ? | 0.20 |
| Vercel Sandbox | Firecracker | Filesystem only | From snapshot | No | No | No | 0.11–0.34 (active CPU) |
| Cloudflare Sandbox | Container in VM | Beta | No | No | No | No | 0.09–0.22 (2 vCPU / 8 GB) |
| Morph Cloud | MicroVM | Yes | Yes | ? | No | ? | ~0.10 |
| Blaxel | MicroVM | Yes (standby) | ? | ? | No | ? | 0.17 |
| Freestyle | VM | Yes | **Yes, live** | ? | No | ? | 0.13 |
| Beam | gVisor / runc / microVM | Yes | ? | Yes | No | ? | 0.14 |
| Northflank | Kata / gVisor | Pause only | ? | Yes | No | ? | 0.067 |
| Fly Sprites | Firecracker | Filesystem checkpoints | ? | ? | No | ? | 0.16 |

\* List price converted to a 100% CPU wall-clock hour on 2026-11-24. These figures are **not comparable without the caveats in [METHODOLOGY §6](../METHODOLOGY.md#6-cost)**: active-CPU billing, fixed CPU:RAM ratios, platform fees, and how a "core" is defined. `?` means unverified.

**Near-universal capabilities (good for the first release):** create, exec and destroy via SDK. A Python or TS SDK. File I/O. Custom OCI images. Outbound internet. Preview URLs. Per-second billing. Filesystem snapshot to a new sandbox.

**Differentiators (later capability tracks):** memory snapshot/resume, live fork, scale-to-zero with auto-wake, GPU, macOS/Windows, desktop/computer use, Docker-in-sandbox, egress allowlists and secret injection, self-host/BYOC, sessions over 24 h.

**Free tiers and credits (enough for an MVP):** Freestyle (generous free monthly allowance), Daytona $200, Blaxel up to $200, E2B $100, Modal $30/mo, plus Vercel and Cloudflare monthly allowances.

### Sources (providers)
[Daytona pricing](https://www.daytona.io/pricing) · [Daytona sandboxes](https://www.daytona.io/docs/en/sandboxes) · [E2B pricing](https://e2b.dev/pricing) · [E2B snapshots](https://docs.e2b.dev/sandbox/snapshots) · [Modal pricing](https://modal.com/pricing) · [Modal sandboxes](https://modal.com/docs/guide/sandboxes) · [Tensorlake limits](https://docs.tensorlake.ai/faqs/pricing-limits-faq) · [Vercel Sandbox pricing](https://vercel.com/docs/sandbox/pricing) · [Cloudflare Containers pricing](https://developers.cloudflare.com/containers/platform/pricing/) · [Runloop pricing](https://www.runloop.ai/pricing) · [Morph plans](https://cloud.morph.so/docs/documentation/setup/plans) · [Blaxel pricing](https://blaxel.ai/pricing) · [Together sandbox](https://docs.together.ai/docs/together-code-sandbox.md) · [Northflank sandboxes](https://northflank.com/product/sandboxes) · [Fly Sprites](https://fly.io/sprites.md) · [Beam pricing](https://www.beam.cloud/pricing) · [Freestyle pricing](https://www.freestyle.sh/pricing) · [ComputeSDK](https://github.com/computesdk/computesdk) · [AWS Lambda MicroVMs](https://aws.amazon.com/lambda/lambda-microvms)
