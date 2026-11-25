# Governance

How providers, contributors and maintainers work together on sandbox-bench.

**The short version:**
- Results can't be bought.
- Everyone runs through the same harness.
- Maintainers own how things are measured.
- Providers are welcome collaborators.

## Divisions

| Division | Rules | Purpose |
|---|---|---|
| `default` | Public SDK at a pinned version, the standard sandbox spec, a publicly available plan, documented defaults | The headline, like-for-like view |
| `optimized` | Any generally available feature or plan (warm pools, bigger tiers…), with the configuration disclosed | A provider's best case |
| `submitted` | Results a provider or community member ran on their own account with the official harness (see below) | Tracks that are too expensive for us to run ourselves |

Beta features are tagged `preview` and kept out of `default`.

## Accounts and credits

- Every configuration runs on the provider's free-tier allowance or on credits the provider gives the project. Each configuration notes which.
- Credits never affect inclusion or ranking.
- Now and then, we re-run provider-given accounts from a plain free-tier account to make sure the numbers match.

## Adapters

- An adapter is a thin module over the provider's public SDK. The harness does all the timing.
- Providers can co-own their adapter (CODEOWNERS). A maintainer still approves each change.
- `provider.yaml` declares capabilities, sandbox type, plan and SDK version. Every claimed capability is checked by a probe on every run.

## Working with providers

- **Heads-up before big releases.** Affected providers get a 7-day preview before a new track or a methodology version ships.
- **Provider notes.** Each provider page has room for a short statement from the provider.
- **Issues.** If something looks off, open an issue with the `dispute` template and we'll work it out in public.
- **Reproducibility.** If results can't be reproduced, we annotate them and may pull them until they can.

## Submitted results *(planned)*

Some tracks cost more than free tiers and donated credits cover, such as GPU fleets, 1,000-sandbox bursts and long soak tests. For those, providers and community members can run the benchmark on their own accounts. This is an early design:

- Run a tagged harness release with unmodified benchmarks and the public adapter.
- Package the results with `sbx submit`. This bundles the manifest, raw samples and logs.
- Open a PR. CI checks the schema, the harness checksum and the declared configuration.
- Results show up in the `submitted` division, labelled with who ran them. Maintainers re-run a sample when credits allow.

This also gives us more client regions for free.

## Quoting results

You're welcome to quote results. Please include:
- the metric and division;
- the harness version and date window;
- a link to the result page.

## Changing the benchmark

- **New benchmark in an existing track:** a PR with a short design note, and approval from two maintainers.
- **New tracks, scoring changes and timing-boundary changes:** an RFC in `docs/rfcs/`, open for 14 days.
- **Every accepted change** goes in `CHANGELOG.md`.

## Terms of service

Before adding a provider, we check its terms for benchmark-publication clauses and ask for permission where needed. We never run anything that would breach acceptable-use terms.
