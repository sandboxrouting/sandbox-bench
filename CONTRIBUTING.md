# Contributing

There are three ways in. Each is one small change.

| You want to… | Do this |
|---|---|
| **Propose a probe** | Open an issue with a one-sentence pass condition |
| **Add your provider** | Add one file, `src/sandbox_bench/providers/<you>.py`, and open a PR |
| **Fix or improve something** | Pick a [`good-first-issue`](https://github.com/sandboxrouting/sandbox-bench/labels/good%20first%20issue) and open a PR |

If a result looks wrong, open an issue with the `dispute` template. One maintainer approval merges a PR.

## Setup

```bash
git clone https://github.com/sandboxrouting/sandbox-bench && cd sandbox-bench
uv sync
uv run pytest        # runs every probe against the fake provider; no cloud account needed
```

## How the repo is laid out

```
src/sandbox_bench/
  providers/          one file per provider
    _template.py      start here
    fake.py           offline provider: passes every probe, or fails any one on request
  probes/             one file per action; each yields one or more probe verdicts
    guest.py          every shell script run inside a sandbox, and its parser
  harness.py          clocks, timeouts, pacing and cleanup around adapter calls
  runner.py           a run: shuffled attempts, warm-up, reaping, the run record
  report.py, boards.py   scoring and the tables
  cli.py              `sbx`
pricing/pricing.yaml  list prices, each with a source link and the date it was checked
docs/                 methodology, roadmap, research
  decisions/          one record per decision, with the alternatives we didn't take
```

The harness is kept under 1,800 lines: everything outside `providers/` and `probes/`, plus the shared probe modules `probes/__init__.py` and `probes/guest.py` ([ADR-0003](docs/decisions/0003-line-budget-counts-shared-probe-code.md)). CI checks it with `scripts/check_budget.py`.

## Add your provider

1. **Copy the template.** Copy `src/sandbox_bench/providers/_template.py` to `src/sandbox_bench/providers/<you>.py` and fill it in:

   ```python
   class Acme(Adapter):
       name = "acme"
       product = "microvm"          # shown as "Acme (microvm)"
       owner = "@your-github-handle"
       access = "sdk"               # or "rest"
       plan = "free tier"
       start_mode = "memory"        # pool | memory | cold
       offers = {                   # every probe your docs claim, with the link that claims it
           "pause-keeps-memory": "https://docs.acme.dev/pause",
           "fork-keeps-memory":  "https://docs.acme.dev/fork",
       }

       def __init__(self): ...                  # read your key from an env var

       # Required
       def create(self, spec): ...              # spec has name, size, egress; return a handle
       def exec(self, sb, cmd, timeout_s): ...  # return ExecResult(exit_code, stdout, stderr)
       def destroy(self, sb): ...

       # Optional: implement what you offer
       def pause(self, sb): ...
       def resume(self, sb): ...
       def snapshot(self, sb, name): ...         # return once the snapshot is usable
       def restore(self, snap, spec): ...        # a new sandbox from the snapshot
       def delete_snapshot(self, snap): ...
       def fork(self, sb, specs): ...            # one copy per spec, in order
       def expose_port(self, sb, port): ...      # return Endpoint(url, headers)
       def ping(self): ...                       # cheapest authenticated call: API RTT
       def reap(self, prefix): ...               # delete everything named prefix*; return the count
   ```

   `uv run sbx validate acme` checks the declarations: every offered probe needs the operations it uses.

2. **Check it:**

   ```bash
   ACME_API_KEY=... uv run sbx check acme           # every probe, one attempt each
   uv run sbx check acme --probe pause-keeps-memory --attempts 5
   ```

   It exits non-zero if any probe failed, and writes the raw run record under `results/`.

3. **Open a PR** and paste the table `sbx check` printed.

After merge, a maintainer adds your keys to the `live` environment, and your provider joins the next published run ([RUNNER](docs/RUNNER.md)), which makes 10 attempts per probe.

**Adapter rules:**
- **Public API only.** Use your public SDK or REST API, with the SDK version pinned.
- **Map, don't optimise.** No retries, pre-warming or caching. The harness does all the timing.
- **Use the harness's helpers.** Poll with `self.wait_until(...)`, and create only resources named from `spec.name` (or `name` for snapshots); that `sbx-` prefix is how cleanup finds them.
- **Credentials.** Read them from environment variables named after your provider (`ACME_API_KEY`, `ACME_API_URL`). Published runs pass a provider only the secrets with its prefix.
- **Errors.** Raise `AccountError` only for problems on our side (missing key, no credits, a plan limit); those attempts are excluded. Any other exception counts as a provider failure, including being throttled for request rate ([ADR-0009](docs/decisions/0009-throttling-is-the-providers-failure.md)).
- **Pacing and timeouts.** Set `pacing_s` from your documented rate limit, with a link to it. Timeouts are the same for everyone.

## Propose a probe

A good probe has a **one-sentence pass condition** that any provider could meet, for example "After pause and resume, the same process is still running and counting".

1. Open an issue with the sentence. We'll agree on the verifier there.
2. Add it to the action file in `src/sandbox_bench/probes/` it belongs to, or create a new one. A probe uses only adapter operations, through `h`, and `sh` inside the sandbox. `h` owns the clocks, timeouts and cleanup:

   ```python
   @action(verdicts=["pause-keeps-files", "pause-keeps-memory"], timings=["start", "pause", "resume"])
   def pause(h: Context) -> dict[str, Check]:
       sb = h.create()                   # timed as Start, until a command succeeds
       before = h.start_counter(sb)      # sh loop + /dev/shm buffer (see METHODOLOGY §3)
       f = h.write_random(sb)            # 10 MiB
       h.pause(sb)                       # until the call returns
       h.resume(sb)                      # until a command succeeds again
       return {
           "pause-keeps-files": h.same_file(sb, f),
           "pause-keeps-memory": h.counter_continued(sb, before),
       }
   ```

   New shell snippets go in `probes/guest.py`, POSIX `sh` only, with a parser that never raises.

3. Add a test where the fake provider passes the probe, and one where it fails: give `providers/fake.py` a failure mode for it in `FAILURES`. `tests/test_probes.py` then runs both.

New probes count from the next benchmark version, after a 7-day notice in an issue.

**Adding a column** to the tables takes one line in `src/sandbox_bench/boards.py`: the metric and the probe that must pass to be shown.

## Record workarounds and judgement calls

Results are only as honest as what we disclose about them. In the same PR as the change:

- **A known weakness** in what a probe or adapter measures (a workaround, a heuristic, an indirect docs claim, an account limit) gets a row in [METHODOLOGY §9](docs/METHODOLOGY.md#9-threats-to-validity), under the category it fits.
- **A choice between real alternatives** gets a decision record in [`docs/decisions/`](docs/decisions/README.md), status `proposed` until a maintainer approves the PR. The code it explains links it in a comment (`# ADR-0002`), and the §9 row links it too.

When in doubt, write it down. A disclosed workaround is a footnote; one found by a provider is a dispute.
