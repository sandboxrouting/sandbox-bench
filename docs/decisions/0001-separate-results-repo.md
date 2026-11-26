# 0001. Results live in a separate repo

- **Status:** accepted
- **Date:** 2026-11-26

## Context
The daily runner needs somewhere durable to keep every run's raw record:
- **Scores need history.** A probe passes at 9 of its last 10 attempts, and a run makes 5, so every report reads earlier runs.
- **Disputes need evidence.** Each number must trace back to raw attempts that anyone can read and link to.
- **The runner can push.** The runner machine holds the provider keys and needs write access somewhere.

## Decision
Raw records and the generated tables go to `sandboxrouting/sandbox-bench-results`, as described in [RUNNER](../RUNNER.md). The runner's deploy key can write only to that repo.

## Alternatives
- **The code repo.** It would get about 365 bot commits a year and a CI run on each. A runner key with write access to the code repo could also change the harness that produces the results.
- **An orphan `results` branch in the code repo.** This keeps the history in one place, but deploy keys apply to the whole repo, so keeping the runner off `main` would depend on branch rules alone.
- **A storage bucket.** It has no public history and no stable per-file links for disputes.
- **The runner's local disk.** The history is lost with the machine.

## Consequences
- There are two repos to keep in sync. The results repo records which harness commit produced each run (`git_sha` in every record).
- A compromised runner can push bad results but not change the harness. Bad results stay visible in public history.
