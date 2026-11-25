# sandbox-bench

**How fast does your sandbox really start? Does it still remember what it was doing after a pause? Can it fork itself ten times without breaking a sweat?**

sandbox-bench is an open benchmark for the cloud sandboxes AI agents run in. It drives E2B, Daytona, Modal, Vercel, Blaxel, Tensorlake, Morph and more through their own SDKs, runs the same workloads on every one, and publishes the results as a live leaderboard. The raw data sits right here in the repo.

> 🚧 **Pre-launch.** v0.1 is under construction. See the [roadmap](docs/ROADMAP.md).

## What we measure

| Track | The question |
|---|---|
| **Lifecycle** | How long until my first command runs? How snappy are exec and file I/O? |
| **State** | How fast are snapshot, restore, pause/resume and fork, and do memory and processes survive them? |
| **Capabilities** | Which features actually work? Every ✓ comes from a probe that passed. |
| **Cost** | What does an hour cost at full tilt, and what does it cost while the agent is waiting on an LLM? |
| **Workloads** *(soon)* | Real work: clone, install and test a repo, plus CPU, disk, network and Terminal-Bench via Harbor. |
| **Scale** *(soon)* | What happens when you ask for 100 sandboxes at once? |
| **GPU · Browser · macOS/Windows** *(later)* | The specialized stuff. |

There is no single winner. Each track has its own leaderboard, and persona views (e.g. "RL rollouts" or "interactive coding agent") let you weight the tracks that matter to you.

## Quickstart

*Coming with v0.1:*

```bash
uv tool install sandbox-bench
sbx run --providers e2b,modal --bench lifecycle/cold-start
```

## Add your sandbox

Run a sandbox platform? Adding it means writing one small adapter over your public SDK. Copy `providers/_template/`, implement `create`, `exec` and `destroy` (plus snapshot, fork and the rest if you support them), and open a PR. See [CONTRIBUTING.md](CONTRIBUTING.md).

Have an idea for a benchmark? Open an issue or start a discussion. New tracks are very welcome.

## Docs

- [Vision](docs/VISION.md): why this exists and where it's going
- [Methodology](docs/METHODOLOGY.md): exactly what gets timed and how results are scored
- [Governance](docs/GOVERNANCE.md): how providers and contributors take part
- [Architecture](docs/ARCHITECTURE.md): harness, adapters and data format
- [Roadmap](docs/ROADMAP.md): what's next
- [Landscape research (Nov 2026)](docs/research/landscape-2026-11.md): what exists today

## License

[Apache 2.0](LICENSE)
