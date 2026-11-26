# Landscape research: November 2026

> Snapshot taken **2026-11-24**. This market changes month to month, so treat every number here as dated.
> Things we could not confirm are marked *unverified*.
> Background for the [README](../../README.md) and the [methodology](../METHODOLOGY.md).

## 1. Existing sandbox comparisons

Published comparisons we read while designing this one, with what each measures.

| Source | What it measures |
|---|---|
| [ComputeSDK Benchmarks](https://www.computesdk.com/benchmarks/sandboxes) ([code](https://github.com/computesdk/benchmarks)) | Time to interactive under a burst of concurrent creates, a clone-and-build workload, and reliability |
| [Lizard: E2B vs Daytona vs Modal](https://lizard.build/blog/e2b-vs-daytona-vs-modal) | Create latency over 300 starts per provider, with percentiles and raw data |
| [Tensorlake sandbox-sqlite-bench](https://github.com/tensorlakeai/sandbox-sqlite-bench) | Filesystem I/O at 2 vCPU / 4 GB |
| [Tensorlake: Accelerating Harbor](https://tensorlake.ai/blog/accelerating-harbor-with-tensorlake) | Terminal-Bench 2 oracle runs on Harbor across providers |
| [Beam benchmarks](https://www.beam.cloud/benchmarks) | Cold start, image pull and volume I/O |
| [LogRocket comparison](https://blog.logrocket.com/comparing-ai-agent-sandbox-platforms-e2b-modal-daytona-and-more/) | Create and resume to first command; notes that "resume" means different things on different providers |
| [Firegoat Agent Arena](https://firegoat.ai/arena/sandboxes) | A coding agent onboarding itself onto each provider, scored on time, cost and errors |
| [nibzard/ai-sandbox-benchmark](https://github.com/nibzard/ai-sandbox-benchmark) | A terminal UI comparing 5 providers |

Feature lists: [awesome-ai-sandboxes](https://github.com/tizkovatereza/awesome-ai-sandboxes), [awesome-sandbox](https://github.com/restyler/awesome-sandbox), [awesome-agent-sandbox](https://github.com/fishman/awesome-agent-sandbox).

### What sandbox-bench focuses on
1. **State operations, verified by running them:** snapshot, restore, pause/resume with **memory preservation**, and live fork. These are among the most advertised sandbox features.
2. **A feature matrix checked by executable tests,** not copied from docs.
3. **Open everything:** the harness, the verifiers and every raw result, so any number can be reproduced or disputed.
4. **Latency kept separate from capacity:** one operation in flight, so a timing never mixes in queueing under load.

### Published claims to test

| Provider | Claim |
|---|---|
| Daytona | "sub-90 ms creation" |
| E2B | "~150 ms" start |
| Blaxel | "<25 ms resume from standby" |
| Morph | Snapshot/branch/restore "<250 ms" |
| Freestyle | Fork "<50 ms", boot "<800 ms" |
| Modal | About 1 s memory-snapshot restore (stated for Functions) |
| Fly Sprites | Warm wake 100–500 ms, checkpoint about 300 ms |
| Runloop | "<2 s for a 10 GB image" |

## 2. Precedents from other benchmarks (patterns we adopt)

| Precedent | What we copy | What we avoid |
|---|---|---|
| **[Harbor](https://docs.harborframework.com) + [Terminal-Bench](https://www.tbench.ai)** | A task directory format (`instruction`, `environment/`, `solution/` as the oracle, `tests/` as the verifier). A provider adapter interface (`start/stop/exec/upload/download`) with a **declared capabilities object**. Versioned datasets. Harbor already ships about 37 sandbox provider integrations, **so Terminal-Bench oracle runs can serve as a real-world workload metric** (every failure is the sandbox's fault). | Letting submitters control the harness (see Terminal-Bench's [leaderboard integrity update](https://www.tbench.ai/news/leaderboard-integrity-update)). |
| **[ClickBench](https://github.com/ClickHouse/ClickBench)** | One directory per system. Results as JSON committed to git. A static site generated from that data. Tuned results labelled and listed separately. `null` for missing results. Score = geometric mean of `(t+shift)/(best+shift)`. Tags so readers compare like-for-like. | A single flat workload. |
| **[Artificial Analysis](https://artificialanalysis.ai/methodology/performance-benchmarking)** (benchmarks LLM *providers*, the closest analog to us) | Scheduled probes (every 6 h). A rolling window of medians. **"Mystery shopper" anonymous accounts** to cross-check accounts the provider supplied. Provider-side errors count against the provider and harness-side errors are excluded. A published **sanctions ladder** for non-representative serving. | Relying on a single region for good. |
| **[MLPerf](https://github.com/mlcommons/policies/blob/master/submission_rules.adoc)** | A **Closed vs Open** division (stock config vs anything-goes but disclosed). **Available vs Preview** tags. A peer-review objection window. A **results-citation policy** for vendor marketing. | A heavy submission process. |
| **[SWE-bench](https://github.com/SWE-bench/experiments)** | Submissions as metadata files in git, plus a CLI for packaging and verification. | |
| **[TechEmpower](https://github.com/TechEmpower/FrameworkBenchmarks)** | Precise per-test rules, and a "Stripped" label for implementations that cut corners. | Implementations written by the systems under test, which invite optimization disputes. So maintainers own the harness, adapters stay thin, and maintainer load needs a budget. |
| **[Shilkov cold-start research](https://mikhail.io/serverless/coldstarts/methodology/)** | Client-side end-to-end timing. Coldness detected rather than guessed. Distributions instead of averages. Results dated because they go stale. | |
| **[OpenRouter](https://openrouter.ai/docs/features/provider-routing)** | Later on: opt-in "observed in production" telemetry alongside our synthetic probes. | |

## 3. Provider landscape (feature snapshot)

**Structural facts that affect the design:**
- **ComputeSDK is not a provider.** It is an MIT-licensed abstraction over E2B, Modal, Daytona, Vercel and others, so it isn't benchmarked as one.
- **Daytona has several sandbox types** (container, Linux VM, Windows VM, macOS) with different feature sets: containers can't fork or take memory snapshots. **So each row is a provider *and product*, e.g. "Daytona (container)", not just a provider.**
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
