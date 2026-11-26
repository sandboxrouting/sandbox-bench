# The runner

The published tables come from one fixed machine in us-east that runs the benchmark once a day (METHODOLOGY §1). This page is how that machine is set up. You don't need any of it to run `sbx check` yourself.

## What a daily run does

[`deploy/daily-run.sh`](../deploy/daily-run.sh), started by a systemd timer at 06:00 UTC:

1. Moves the harness checkout to the tip of `main` and installs its locked dependencies.
2. Runs `sbx run` for every configured provider: one warm-up create each, then 5 attempts per offered probe, shuffled, one operation in flight.
3. Writes the raw run record to the results repo at `runs/YYYY/MM/DD/<run_id>.json`.
4. Rebuilds the tables there with `sbx report runs --out board`, commits and pushes.

A provider failing its probes is a result, so it never stops the run or the push. Only a harness error makes `sbx run` exit non-zero, and whatever it recorded is still published.

## The results repo

A separate git repository ([ADR-0001](decisions/0001-separate-results-repo.md)):

- **Scores need history.** A probe is scored on its last 10 attempts and a run makes 5, so every report reads earlier runs from here.
- **Every number is traceable.** A disputed result links to the raw record behind it, and git history shows any change to it.
- **The runner can't touch the code.** Its deploy key writes only to this repo, so a compromised runner could publish bad results but not change the harness.
- **The code repo stays readable,** without a bot commit and a CI run every day.


```
runs/2026/12/01/20261201-0600-a1b2.json   raw RunRecords, never edited
board/leaderboard.md                      the main table
board/results.json                        aggregates, machine-readable
```

Records are append-only. A fix to the scoring rebuilds `board/` from `runs/`; it never rewrites a record.

## Setting up the machine

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
  --setenv=SBX_PUSH=0 /home/sbx/sandbox-bench/deploy/daily-run.sh
```

This loads the keys the same way the service does, so they never show up in your shell history or `ps`.

## Operating it

| To… | Run |
|---|---|
| See the next and last runs | `systemctl list-timers sandbox-bench.timer` |
| Read a run's log | `journalctl -u sandbox-bench.service --since today` |
| Start a run now | `systemctl start sandbox-bench.service` |
| Delete leftovers on one provider | `sudo systemd-run --wait --pty --uid=sbx -p EnvironmentFile=/etc/sandbox-bench/env -p WorkingDirectory=/home/sbx/sandbox-bench /home/sbx/.local/bin/uv run sbx reap <provider>` (only `sbx-` resources) |

**Keys:** they live only in `/etc/sandbox-bench/env` (root, `0600`), reach `sbx` only through the service's environment, and never appear in logs or records. Rotate one by editing that file; the next run picks it up.

**Credits:** an expired key or exhausted credits shows up as excluded attempts in the run log, not as provider failures (METHODOLOGY §5). Check the log after a provider's numbers stop moving.
