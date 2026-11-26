# sandbox-bench

**How fast does your sandbox really start? Does it still remember what it was doing after a pause? Can it fork itself ten times without breaking a sweat?**

sandbox-bench is an open benchmark for the cloud sandboxes AI agents run in. It drives E2B, Daytona, Modal, Vercel, Blaxel, Tensorlake, Morph and more through their own SDKs, puts every one through the same probes and speed races, and publishes the results as a live leaderboard. The raw data sits right here in the repo.

> 🚧 **Pre-launch.** v0.1 is under construction. See the [roadmap](docs/ROADMAP.md).

## How it works

**1. The probe suite: what can it do?**
Every sandbox faces the same versioned set of pass/fail **probes**, each judged by an automated verifier. The main leaderboard ranks providers by how many they pass.

| Category | Probes in `core-v0.1` |
|---|---|
| **Lifecycle** | create → exec · 10 MiB file round-trip · runs our pinned toolset · survives 1 hour |
| **State** | snapshot keeps files / **memory** · pause keeps files / **memory** · fork keeps **memory** · 10 forks stay isolated |
| **Environment** | builds from a Dockerfile · internet · egress block enforced · exposed port reachable · Docker inside |
| **Specialized** *(next)* | Chromium via CDP · desktop screenshot · GPU matmul · ARM64 · macOS · Windows |

**2. Performance boards: how fast, and how cheap?**
These are speed races on start time, start with toolset, exec, file I/O, snapshot/restore, pause/resume, fork ×10 and $/hour. **You only get on a board if you pass its probe.** No working fork, no place on the fork board.

```
 #  Provider     Probes        Start     Resume    Fork×10   $/h
 1  Provider A   94%  14/15    0.7s ⚡   0.1s 🧠   0.9s 🧠   0.13
 2  Provider B   82%  12/15    0.4s ⚡   0.6s      2.1s 🧠   0.17
 3  Provider C   67%   9/15    0.9s      —         —         0.11
                                  ⚡ warm start   🧠 memory kept   (illustrative)
```

## Quickstart

*Coming with v0.1:*

```bash
uv tool install sandbox-bench
sbx run --providers e2b,modal
sbx probe e2b --probe state/pause-keeps-memory
```

## Add your sandbox

Run a sandbox platform? Adding it means writing one small adapter over your public SDK. Copy `providers/_template/`, implement `create`, `exec` and `destroy` (plus snapshot, fork and the rest if you support them), and open a PR. Every feature you support is a probe you can pass. See [CONTRIBUTING.md](CONTRIBUTING.md).

Have an idea for a probe? Open an issue or start a discussion. Harder probes make a better benchmark.

## Docs

- [Vision](docs/VISION.md): why this exists and where it's going
- [Methodology](docs/METHODOLOGY.md): exactly what gets timed and how results are scored
- [Governance](docs/GOVERNANCE.md): how providers and contributors take part
- [Architecture](docs/ARCHITECTURE.md): harness, adapters and data format
- [Roadmap](docs/ROADMAP.md): what's next
- [Landscape research (Nov 2026)](docs/research/landscape-2026-11.md): what exists today

## License

[Apache 2.0](LICENSE)
