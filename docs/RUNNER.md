# The runner

Published results come from one GitHub Actions workflow, started by a maintainer ([ADR-0010](decisions/0010-manual-runs-from-one-workflow.md)). This page covers how a run is started, what it does, and where its results go. You don't need any of it to run `sbx check` yourself.

## Starting a published run

From `main` only, by a maintainer:

```bash
gh workflow run benchmark.yml -f providers=daytona,freestyle
```

Or use **Actions → Benchmark run → Run workflow** on GitHub. The `live` environment asks a maintainer to approve the run before any key is used.

## What a run does

[`.github/workflows/benchmark.yml`](../.github/workflows/benchmark.yml) runs [`deploy/publish-run.sh`](../deploy/publish-run.sh) on a GitHub-hosted Linux runner:

1. Records the runner's Azure region. GitHub doesn't pin it, so each run says where it ran.
2. Runs `sbx run` for the chosen providers: one warm-up create each, then 10 attempts per offered probe, shuffled, with one operation in flight.
3. Writes the raw run record to the results repo at `runs/YYYY/MM/DD/<run_id>.json`.
4. Rebuilds the tables there with `sbx report runs --out board`.
5. Commits, naming who started the run with a link to its log, and pushes.
6. Deletes any `sbx-` leftovers on each provider, even if the run failed.

A provider failing its probes is a result, so it never stops the run or the push. Only a harness error makes `sbx run` exit non-zero, and whatever it recorded is still published. Every run started is published: there is no way to run and then decide.

**One-time setup:**
- A `live` environment, with required reviewers, holding:
  - each provider's keys, named after it: `DAYTONA_API_KEY`, `DAYTONA_API_URL`, `E2B_API_KEY`, `FREESTYLE_API_KEY`;
  - `RESULTS_DEPLOY_KEY`, the private half of a deploy key with write access on the results repo.

  For a new provider, add its keys here and one line per key to the "Pass the provider's keys" step in `benchmark.yml` and `live-check.yml`. That step lists keys by name: GitHub flags a workflow that reads all secrets at once (`toJSON(secrets)`) as possibly malicious and won't run it. A run then passes each provider only the keys whose names start with its own (`DAYTONA_…`), via [`scripts/export_provider_secrets.py`](../scripts/export_provider_secrets.py).
- On E2B, the standard-size template, built once with the account's key: `E2B_API_KEY=... uv run python -m sandbox_bench.providers.e2b build-template` ([ADR-0011](decisions/0011-e2b-standard-size-template.md)). Rebuild it when the `e2b` SDK pin changes.

## The results repo

A separate git repository ([ADR-0001](decisions/0001-separate-results-repo.md)):

- **Scores need history.** Every report is rebuilt from all the records kept here.
- **Every number is traceable.** A disputed result links to the raw record behind it, and git history shows any change to it.
- **The runner can't touch the code.** Its deploy key writes only to this repo, so a compromised runner could publish bad results but not change the harness.
- **The code repo stays readable,** without a bot commit and a CI run for every benchmark run.

```
runs/2026/12/01/20261201-0600-a1b2.json   raw RunRecords, never edited
board/leaderboard.md                      the main table
board/results.json                        aggregates, machine-readable
```

Records are append-only. A fix to the scoring rebuilds `board/` from `runs/`; it never rewrites a record.

## Planned: daily runs on a fixed machine

Once the project has users, runs move to a daily schedule on one fixed machine in us-east, which also pins the region. Everything for that is ready in `deploy/`: the same `publish-run.sh`, started by a systemd timer at 06:00 UTC. (A `schedule:` trigger on the workflow is the lighter option, but its region stays unpinned.)

### Setting up the machine

Any small Linux VM in us-east (2 vCPU is plenty: the runner only waits on APIs).

```bash
# as root
useradd --create-home sbx
install -d -m 0755 /etc/sandbox-bench
install -m 0600 deploy/env.example /etc/sandbox-bench/env   # then fill in the keys

# as sbx
curl -LsSf https://astral.sh/uv/install.sh | sh
git clone https://github.com/sandboxrouting/sandbox-bench ~/sandbox-bench
git clone git@github.com:sandboxrouting/sandbox-bench-results ~/sandbox-bench-results   # a deploy key with write access

# as root
cp ~sbx/sandbox-bench/deploy/systemd/sandbox-bench.{service,timer} /etc/systemd/system/
systemctl daemon-reload
systemctl enable --now sandbox-bench.timer
```

Try one run by hand before trusting the timer, with pushing off:

```bash
sudo systemd-run --wait --pty --uid=sbx -p EnvironmentFile=/etc/sandbox-bench/env \
  --setenv=SBX_PUSH=0 /home/sbx/sandbox-bench/deploy/publish-run.sh
```

This loads the keys the same way the service does, so they never show up in your shell history or `ps`.

### Operating it

| To… | Run |
|---|---|
| See the next and last runs | `systemctl list-timers sandbox-bench.timer` |
| Read a run's log | `journalctl -u sandbox-bench.service --since today` |
| Start a run now | `systemctl start sandbox-bench.service` |
| Delete leftovers on one provider | `sudo systemd-run --wait --pty --uid=sbx -p EnvironmentFile=/etc/sandbox-bench/env -p WorkingDirectory=/home/sbx/sandbox-bench /home/sbx/.local/bin/uv run sbx reap <provider>` (only `sbx-` resources) |

**Keys:** they live only in `/etc/sandbox-bench/env` (root, `0600`), reach `sbx` only through the service's environment, and never appear in logs or records. Rotate one by editing that file; the next run picks it up.

**Credits:** an expired key or exhausted credits shows up as excluded attempts in the run log, not as provider failures (METHODOLOGY §5). Check the log after a provider's numbers stop moving.
