# Contributing

Thanks for helping out! Whether you run a sandbox platform, build agents, or just have a good probe idea, there's a place for you here. [GOVERNANCE.md](docs/GOVERNANCE.md) explains how providers, contributors and maintainers work together.

## Ways to contribute

| You want to… | Do this |
|---|---|
| Suggest a probe | Open a Discussion in **Probe ideas**, or an issue with the `new-probe` template |
| Request a provider | Open an issue with the `new-provider` template |
| Add a provider adapter | Follow the checklist in [ARCHITECTURE.md](docs/ARCHITECTURE.md#extensibility-checklists). One folder under `providers/`. |
| Add a probe or a board | One folder under `probes/<category>/` or `boards/`, plus a design note in the PR. See the checklists in [ARCHITECTURE.md](docs/ARCHITECTURE.md#extensibility-checklists). |
| Propose a new category or change scoring or timing | Write an RFC in `docs/rfcs/`. It stays open for comment for 14 days. |
| Submit results you ran on your own account (planned for v0.3) | Run a tagged harness release, package the output with `sbx submit`, and open a PR. Results appear in the `submitted` division. See [GOVERNANCE](docs/GOVERNANCE.md#submitted-results-planned). |
| Think a result looks wrong | Open an issue with the `dispute` template and we'll dig in together. |

## Rules for adapters

- Use the provider's **public** SDK, pinned to a version.
- Keep adapters thin. Adapters must not retry, pre-warm, cache, or do their own timing; the harness does all timing.
- Declare capabilities in `provider.yaml`. Probes check them on every run.
- Vendor employees are welcome to contribute. Disclose your affiliation in the PR. Merging still needs approval from a non-vendor maintainer.

## Development

The harness is not built yet; it is part of the [v0.1 plan](docs/ROADMAP.md). This section will be filled in once the harness exists.
