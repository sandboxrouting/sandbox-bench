# Vision

## One sentence

**sandbox-bench is a neutral, open-source benchmark for cloud sandbox providers used by AI agents. It measures what matters, publishes every raw sample, and lets each team decide which provider fits its workload.**

## The problem

Agent builders now choose between 15+ sandbox providers: E2B, Daytona, Modal, Vercel, Cloudflare, Blaxel, Tensorlake, Morph, Freestyle, Beam, Northflank, Fly Sprites, and new ones every month. Today the choice is made on:

- **Vendor claims nobody has reproduced.** "Sub-90 ms creation" became 483–819 ms in third-party tests, and "~150 ms" became 264–1041 ms.
- **Benchmarks run by people with a stake in the result.** These include vendors ranking themselves first, a router that sells sponsor placements and private benchmarks, and sites that sell "reports to improve your rank".
- **Create latency only.** The operations that make agent workloads cheap and robust are snapshot/restore, pause/resume *with memory intact*, and fork. They are the most heavily marketed features and nobody independently checks them.
- **Feature matrices copied from docs.** A matrix says "supports fork" but nothing checks that it works.

(Evidence and sources: [research/landscape-2026-11.md](research/landscape-2026-11.md).)

## What we are building

1. **A harness.** It calls each provider through its own native SDK and puts the same standard workloads through each one.
2. **Tracks.** These are independent families of benchmarks (lifecycle, state, workloads, scale, GPU, browser, cost…). A provider is only ranked in the tracks it supports.
3. **A verified capability matrix.** Every "✓" comes from an executable probe that passed, not from a docs page.
4. **An open dataset.** Every sample, with harness version, SDK version, region, plan and timestamp, is committed to git.
5. **A static website.** It offers per-track leaderboards, persona views ("best for RL rollouts", "best for interactive coding agents"), provider profiles with history, and a methodology page that matches the code.

## Who it serves and why they come back

| Audience | What they get | Why they come back |
|---|---|---|
| **Agent builders / platform teams** | A trustworthy shortlist for their workload, with distributions rather than marketing numbers | Data refreshes continuously, and history shows who is improving |
| **Sandbox providers** | (a) A neutral place where buyers already look, so being *absent* costs them. (b) A per-metric breakdown of where they lag, i.e. a free performance team. (c) Public credit when they improve ("Provider X cut resume p50 by 40% this month"). (d) Verified capability badges they can cite. | Regression alerts, an "Optimized" division to show their best config, and a seat at the table when new tracks are designed |
| **Researchers / community** | A clean, versioned dataset and an easy way to propose new benchmarks | A low-friction RFC process and recognition for contributors |

The vendor incentive is the flywheel. **If builders trust the numbers, vendors have to be listed, and to be listed they help us keep adapters correct.** So trust is the product, and every design decision should protect it.

## Positioning versus what exists

| | Typical existing benchmark | sandbox-bench |
|---|---|---|
| Operator | Vendor or router with a commercial stake | Non-profit, with funding disclosed, no paid placement and no paid private benchmarks |
| Client | One abstraction layer | Each provider's **native SDK**, pinned and public |
| Metrics | Create latency, sometimes a composite | Lifecycle, **state ops (snapshot, restore, pause/resume, fork) with correctness checks**, workloads, cost, verified capabilities |
| Statistics | Median or best-of-N, no date | Full distributions, confidence intervals, success rate shown next to every latency figure, dated runs, history |
| Data | Website only | Every raw sample in git, with one-command reproduction |
| Ranking | One global score | Per-track ranks with **statistical-tie bands**, and persona views with visible, adjustable weights |
| Vendors | Passive subjects or paying sponsors | Right of reply, public dispute process, citation policy |

## Principles (non-negotiable)

1. **Neutral.** No paid placement, no sponsor logos in result tables, and no private benchmarks for sale. Funding and conflicts of interest are disclosed.
2. **Transparent.** Methodology is code, all data is public, and every chart links to the samples behind it.
3. **Fair.** Native SDKs, comparable resource sizes, the same workloads, and the same rules for everyone. Failures count against the provider and harness bugs do not.
4. **Honest about uncertainty.** Distributions over single numbers, ties where confidence intervals overlap, and a date on everything.
5. **Pluralistic.** No single "best sandbox". Workloads differ, so rankings are per track and per persona.
6. **Extensible.** Adding a provider or a benchmark is a small, well-documented PR, and new tracks go through an open RFC.
7. **Sustainable.** Start small, automate everything, and budget maintainer time. (TechEmpower was archived in 2026 after maintainer burnout.)

## Non-goals (for now)

- Benchmarking self-hosted runtimes (Firecracker, gVisor, microsandbox) outside a provider. This could become a separate track later.
- Security penetration testing of providers. We only verify *documented* isolation and egress behavior, non-destructively and within each provider's terms of service.
- Commercial services: consulting, paid reports, or paid "claimed profiles".
- A subjective review site. Every published number must come from a reproducible measurement.

## What success looks like

**At launch (v0.1):**
- 6–8 provider configurations measured continuously on two tracks (Lifecycle, State).
- At least one vendor replies publicly or opens a PR.
- The site is cited in at least one "which sandbox should I use" discussion.

**At 6 months:**
- 12+ configurations and 5+ tracks.
- Vendors maintain their own adapters under our review.
- Outside contributors have added at least two benchmarks.
- Vendors quote our numbers under the citation policy.
