# Contributing

Thank you for helping make sandbox-bench useful and trustworthy. Please read [GOVERNANCE.md](docs/GOVERNANCE.md) first. It explains what vendors and contributors can change, and what only maintainers can change.

## Ways to contribute

| You want to… | Do this |
|---|---|
| Suggest a benchmark idea | Open a Discussion in **Ideas**, or an issue with the `new-benchmark` template |
| Request a provider | Open an issue with the `new-provider` template |
| Add a provider adapter | Follow the checklist in [ARCHITECTURE.md](docs/ARCHITECTURE.md#extensibility-checklists). One folder under `providers/`. |
| Add a benchmark to an existing track | One folder under `benchmarks/`, plus a design note in the PR |
| Propose a new track or change scoring or timing | Write an RFC in `docs/rfcs/`. It stays open for comment for 14 days. |
| Submit results you ran on your own account (planned for v0.3) | Run a tagged harness release, package the output with `sbx submit`, and open a PR. Results appear in the `submitted` division. See [GOVERNANCE §7](docs/GOVERNANCE.md#7-vendor-submitted-results). |
| Dispute a result | Open an issue with the `dispute` template. Disputes are handled in public. |

## Rules for adapters

- Use the provider's **public** SDK, pinned to a version.
- Keep adapters thin. Adapters must not retry, pre-warm, cache, or do their own timing; the harness does all timing.
- Declare capabilities honestly in `provider.yaml`. Probes check them on every run.
- Vendor employees are welcome to contribute. Disclose your affiliation in the PR. Merging still needs approval from a non-vendor maintainer.

## Development

The harness is not built yet; it is part of the [v0.1 plan](docs/ROADMAP.md). This section will be filled in once the harness exists.
