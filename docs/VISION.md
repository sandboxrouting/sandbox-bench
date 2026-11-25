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
2. **A probe suite.** It is a versioned set of pass/fail probes covering lifecycle, state, environment and specialized features, each judged by an automated verifier. The main ranking is by probe score.
3. **Performance boards.** Speed and cost races, e.g. start, resume, fork and $/hour. Only providers that pass the matching probe are ranked.
4. **An open dataset.** Every sample is in git, so anyone can slice it their own way.
5. **A website.** It has the main leaderboard, the probe matrix, a page per board, provider pages with history, and side-by-side comparisons.

## Who it's for

- **Agent builders** get a shortlist that fits their workload, and can see who is improving month over month.
- **Sandbox providers** see where they stand on each metric and what to improve next. They get credit when the numbers move, and verified badges they can point to.
- **The community** gets an easy place to propose new probes and a clean dataset to dig into.

Builders come to compare, so providers want to be listed. Providers want to be listed, so they help keep adapters sharp and propose new probes for the features they're proud of. That loop is what grows the benchmark.

## How we work

Results can't be bought. Every provider runs through the same harness and rules, and the data is public. Beyond that, we'd rather the numbers speak.

Day to day, that means:

- **Measure what agents actually do.** Use real operations and real workloads, and treat correctness as part of the result.
- **Show the whole picture.** Every rank comes with its distribution, success rate and date.
- **Make adding things easy.** A new provider, probe or board should be a small PR.
- **Ship small, iterate fast.** Launch narrow, then grow where people pull.

## Not (yet) in scope

- Self-hosted runtimes outside a provider, such as Firecracker, gVisor or microsandbox. This may become its own suite later.
- Security penetration testing. We check documented behavior, such as egress rules, without attacking anyone's infrastructure.
- Opinion-based reviews. If it's on the site, it was measured.

## What success looks like

**At launch:**
- 6–8 provider configurations measured daily on the `core-v0.1` suite and boards.
- At least one provider engages: a reply, a PR or a note.
- People start linking to the site when someone asks "which sandbox should I use?"

**At six months:**
- 12+ configurations, a `specialized` probe category, and workload and scale boards.
- Providers maintain their own adapters.
- Outside contributors have added new probes and boards.
- Providers quote our numbers.
