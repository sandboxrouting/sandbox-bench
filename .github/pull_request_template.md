## What

<!-- One or two sentences. -->

## Checklist

- [ ] `uv run ruff check . && uv run ruff format --check . && uv run mypy && uv run pytest` passes
- [ ] Docs updated where behaviour changed (METHODOLOGY wins over code only if the code is the bug)
- [ ] Any workaround or judgement call is recorded: a row in METHODOLOGY §9, and a record in `docs/decisions/` if it was a choice between alternatives

**Adding a provider?** Also:

- [ ] Every probe in `offers` links to the docs that claim it
- [ ] `sbx check <provider>` table pasted below
- [ ] The provider's terms allow publishing benchmark results
