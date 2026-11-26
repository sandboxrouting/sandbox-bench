# 0010. Published runs are started by hand, from one workflow

- **Status:** accepted
- **Date:** 2026-11-26

## Context
The plan was a fixed machine in us-east running the benchmark every day. Before launch, we don't know yet whether people will use the results. Daily runs cost provider credits and a machine, and they need upkeep: watching for failed runs, fixing adapters when SDKs change, topping up credits.

Scores were built around that daily cadence: 5 attempts per run, scored on the last 10, so a board covered about two days. With runs started by hand, the last 10 attempts could be weeks apart.

## Decision
- **One workflow publishes.** Every published run comes from the `Benchmark run` GitHub Actions workflow (`.github/workflows/benchmark.yml`), started by a maintainer, from `main` only.
- **Nothing started is withheld.** The workflow commits every run it starts to the results repo, with who started it and a link to the run's log.
- **10 attempts per run.** Each run is a complete, dated result on its own.
- **Local runs stay local.** `sbx check` and `sbx run` on a maintainer's machine are for development and are never published.
- **Daily runs are still the plan.** The fixed machine and its daily timer stay in `deploy/`, ready for when the project has users (ROADMAP, "After v0.1").

## Alternatives
- **Daily runs on a fixed machine now.** This gives the freshest results and shows reliability over time, but costs money and upkeep before anyone has asked for the results.
- **Maintainers run locally and push results.** This needs no infrastructure, and the pass/fail scores barely depend on where a run happens. But:
  - Timings include the network path from the runner, so results from different places can't be compared or mixed in one median.
  - Laptop sleep, Wi-Fi drops and VPNs cause timeouts, and timeouts count against the provider.
  - Each maintainer's provider accounts can sit on different tiers. On Daytona, the tier alone decides `internet` and `egress-block`.
  - Every provider key ends up on every maintainer's machine.
  - Reruns after a surprising result could be published selectively, even without meaning to.
  - Outsiders can't check any of it.
- **Manual runs with 5 attempts each.** Fewer credits per run, but a provider's last 10 attempts would span two runs that could be weeks apart.

## Consequences
- **The runner's region isn't pinned.** GitHub-hosted runners are Azure VMs in US regions in practice, but GitHub doesn't guarantee one. Each run records its region, and timings can shift between runs because of it. Listed in [METHODOLOGY §9.3](../METHODOLOGY.md#93-external-validity-how-far-the-results-carry).
- **"Passes 9 of 10" means it worked in one run.** It doesn't show that it keeps working. Each board shows the date of its run. Listed in [METHODOLOGY §9.4](../METHODOLOGY.md#94-conclusion-validity-are-the-numbers-solid-enough).
- **A run costs twice as many credits as before,** but runs are rare.
- **Going daily is one line:** a `schedule:` trigger on the workflow, or the systemd timer in `deploy/` on a fixed machine.
