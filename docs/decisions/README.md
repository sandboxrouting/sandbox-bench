# Decisions

One file per decision that shapes what the benchmark measures or how it runs, numbered in order. A decision is recorded when there was a real alternative. A known weakness of the measurement goes in [METHODOLOGY §9](../METHODOLOGY.md#9-threats-to-validity), and links here when a decision caused it.

| # | Decision | Status |
|---|---|---|
| [0001](0001-separate-results-repo.md) | Results live in a separate repo | accepted |
| [0002](0002-daytona-fresh-client-after-idle.md) | Daytona: a fresh SDK client after 240 s idle | proposed |
| [0003](0003-line-budget-excludes-probes.md) | The line budget doesn't count `probes/` | proposed |
| [0004](0004-egress-needs-a-response.md) | Egress counts as open only if a response comes back | proposed |
| [0005](0005-freestyle-fork-isolation-offered.md) | Freestyle offers `fork-isolation-x3` | proposed |
| [0006](0006-paid-plans-allowed.md) | Accounts may be pay-as-you-go | proposed |
| [0007](0007-unknown-prices-stay-unknown.md) | A price the provider doesn't publish is shown as unknown | proposed |
| [0008](0008-network-probes-use-image-tools.md) | Network probes use tools from the default image | proposed |

## How to add one

Copy the template into `NNNN-short-title.md` with the next number, add a row above, and open a PR. Code that a decision explains links to it in a comment (`# ADR-0002`).

**Statuses:**
- **proposed:** written up, waiting for a maintainer.
- **accepted:** merged with a maintainer's approval.
- **superseded by NNNN:** replaced. The file stays; history isn't edited.

```markdown
# NNNN. Title, stated as the decision

- **Status:** proposed
- **Date:** YYYY-MM-DD

## Context
What forced a choice, with the evidence (measurements, docs links, dates).

## Decision
What we do, in one or two sentences.

## Alternatives
Each option we didn't take, and why not.

## Consequences
What this costs or risks, and where it shows (code, METHODOLOGY §9, the results).
```
