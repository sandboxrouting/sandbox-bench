# Vision

**sandbox-bench is the place to compare cloud sandboxes for AI agents: real measurements, every workload that matters, and every raw sample public.**

## Why

There are now more than 15 sandbox providers: E2B, Daytona, Modal, Vercel, Cloudflare, Blaxel, Tensorlake, Morph, Freestyle, Beam, Northflank, Fly Sprites, and more every month. Picking one usually comes down to launch posts and docs pages.

The features that matter most for agents are the ones that are hardest to compare:

- snapshot and restore;
- pause and resume with memory intact;
- forking a running sandbox;
- cost when an agent spends most of its time waiting on an LLM.

Almost nobody measures these. We do.

(More context: [research/landscape-2026-11.md](research/landscape-2026-11.md).)

## What we're building

1. **A harness.** It talks to each provider through its own SDK and runs the same workloads everywhere.
2. **Tracks.** These are families of benchmarks: lifecycle, state, workloads, scale, GPU, browser, cost. A provider is ranked only in the tracks it supports.
3. **A capability matrix.** Each ✓ means a probe passed, not that a docs page says so.
4. **An open dataset.** Every sample is in git, so anyone can slice it their own way.
5. **A website.** It has leaderboards per track, persona views, provider pages with history, and side-by-side comparisons.

## Who it's for

- **Agent builders** get a shortlist that fits their workload, and can see who is improving month over month.
- **Sandbox providers** see where they stand on each metric and what to improve next. They get credit when the numbers move, and verified badges they can point to.
- **The community** gets an easy place to propose new benchmarks and a clean dataset to dig into.

Builders come to compare, so providers want to be listed. Providers want to be listed, so they help keep adapters sharp and suggest new tracks. That loop is what grows the benchmark.

## How we work

Results can't be bought. Every provider runs through the same harness and rules, and the data is public. Beyond that, we'd rather the numbers speak.

Day to day, that means:

- **Measure what agents actually do.** Use real operations and real workloads, and treat correctness as part of the result.
- **Show the whole picture.** Show distributions, success rates and dates, not a single magic number.
- **Make adding things easy.** A new provider or benchmark should be a small PR.
- **Ship small, iterate fast.** Launch narrow, then grow where people pull.

## Not (yet) in scope

- Self-hosted runtimes outside a provider, such as Firecracker, gVisor or microsandbox. This may become a track later.
- Security penetration testing. We check documented behavior, such as egress rules, without attacking anyone's infrastructure.
- Opinion-based reviews. If it's on the site, it was measured.

## What success looks like

**At launch:**
- 6–8 provider configurations measured daily on lifecycle and state.
- At least one provider engages: a reply, a PR or a note.
- People start linking to the site when someone asks "which sandbox should I use?"

**At six months:**
- 12+ configurations and 5+ tracks.
- Providers maintain their own adapters.
- Outside contributors have added new benchmarks.
- Providers quote our numbers.
