# sandbox-bench

**A neutral, open-source benchmark for the cloud sandboxes that AI agents run in.**

Choosing between E2B, Daytona, Modal, Vercel, Blaxel, Tensorlake, Morph and a dozen others currently means comparing vendor claims that nobody has reproduced. sandbox-bench measures the providers independently. It uses each vendor's native SDK and runs the same workloads on all of them. Every raw sample is published.

> **Status: pre-launch (v0.1 in progress).** Read the [roadmap](docs/ROADMAP.md) for scope and timeline.

## What it measures

| Track | Question it answers | Status |
|---|---|---|
| **Lifecycle** | How long until I can run a command? How fast are exec and file I/O? | v0.1 |
| **State** | How fast are snapshot/restore, pause/resume and fork? **Do memory and processes actually survive them?** | v0.1 |
| **Capabilities** | Which features does each provider have, *checked by executable probes* rather than copied from docs? | v0.1 (partial) |
| **Cost** | What does an hour cost, at full CPU and in a realistic idle-heavy agent profile? | v0.1 (list price) → v0.3 (measured) |
| **Workloads** | How do real tasks perform, such as repo clone/install/test, CPU, disk, network, and Terminal-Bench via Harbor? | v0.2 |
| **Scale** | What success rate and latency do I get under burst and sustained concurrency? | v0.2 |
| **GPU · Browser · macOS/Windows** | Are specialized environments available, how fast are they, and what do they cost? | v0.4 |

## Principles

- **Neutral.** No paid placement, sponsor logos in results, or private benchmarks for sale. Funding and conflicts of interest are disclosed.
- **Transparent.** The methodology is code, every sample is in git, and results can be reproduced with one command.
- **Fair.** Native SDKs and comparable sizes for everyone. A success rate is shown next to every latency, and unsupported features are marked N/A rather than scored zero.
- **Honest.** We show distributions and confidence intervals, rank providers that are statistically tied together, and date every number.
- **Pluralistic.** There is no single "best sandbox". The site has per-track leaderboards and persona views with weights you can adjust.

## Documentation

- [Vision](docs/VISION.md): why this exists, who it serves, and how it differs from existing benchmarks.
- [Methodology](docs/METHODOLOGY.md): timing boundaries, correctness checks, statistics, cost model and scoring.
- [Governance](docs/GOVERNANCE.md): neutrality charter, divisions, right of reply, anti-gaming rules, citation policy.
- [Architecture](docs/ARCHITECTURE.md): harness design, adapter and benchmark interfaces, data schema.
- [Roadmap](docs/ROADMAP.md): the v0.1 action plan and later releases.
- [Landscape research (Nov 2026)](docs/research/landscape-2026-11.md): existing benchmarks, precedents and provider features.

## Contributing

Ideas for new benchmarks, provider requests and adapter PRs are all welcome. Sandbox vendors are especially welcome to review their own adapters. See [CONTRIBUTING.md](CONTRIBUTING.md).

## License

[Apache 2.0](LICENSE)
