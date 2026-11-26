# Contributing

There are three ways in. Each is one small change.

| You want to… | Do this |
|---|---|
| **Propose a probe** | Open an issue with a one-sentence pass condition |
| **Add your provider** | Add one file, `providers/<you>.py`, and open a PR |
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
providers/            one file per provider
  _template.py        start here
  fake.py             offline provider: passes some probes and fails others, used by the tests
probes/               one file per action; each yields one or more probe verdicts
src/sandbox_bench/    the harness: runner, timing, verifiers, report (kept under ~1,500 lines)
pricing/pricing.yaml  list prices, each with a source link and the date it was checked
docs/                 methodology, roadmap, research
```

## Add your provider

1. **Copy the template.** Copy `providers/_template.py` to `providers/<you>.py` and fill it in:

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

       # Required
       def create(self, spec): ...              # spec has name, size, egress; return a handle
       def exec(self, sb, cmd, timeout_s): ...  # return exit code + output
       def destroy(self, sb): ...

       # Optional: implement what you offer
       def pause(self, sb): ...
       def resume(self, sb): ...
       def snapshot(self, sb): ...
       def restore(self, snap, spec): ...
       def fork(self, sb, n): ...
       def expose_port(self, sb, port): ...      # return a reachable URL
   ```

2. **Check it:**

   ```bash
   ACME_API_KEY=... uv run sbx check acme           # every probe
   uv run sbx check acme --probe pause-keeps-memory
   ```

3. **Open a PR** and paste the table `sbx check` printed.

After merge, your provider joins the next daily run on our machine. It shows up in the published tables once each probe has 10 attempts.

**Adapter rules:**
- **Public API only.** Use your public SDK or REST API, with the SDK version pinned.
- **Map, don't optimise.** No retries, pre-warming or caching. The harness does all the timing.
- **Use the harness's helpers.** Poll with `self.wait_until(...)`, and create only resources named from `spec.name`; that `sbx-` prefix is how cleanup finds them.
- **Pacing and timeouts.** Set `pacing` if your API has a documented rate limit. Timeouts are the same for everyone.

## Propose a probe

A good probe has a **one-sentence pass condition** that any provider could meet, for example "After pause and resume, the same process is still running and counting".

1. Open an issue with the sentence. We'll agree on the verifier there.
2. Add it to the action file in `probes/` it belongs to, or create a new one. A probe uses only adapter methods and `sh` inside the sandbox:

   ```python
   @action(verdicts=["pause-keeps-files", "pause-keeps-memory"], timings=["pause", "resume"])
   def pause_resume(h, sb):
       before = h.start_counter(sb)      # sh loop + /dev/shm buffer (see METHODOLOGY §3)
       f = h.write_random(sb, 10 * MiB)
       h.timed("pause", sb.pause)
       h.timed("resume", sb.resume)
       return {
           "pause-keeps-files": h.same_file(sb, f),
           "pause-keeps-memory": h.counter_continued(sb, before),
       }
   ```

3. Add a test where the fake provider passes the probe, and one where it fails.

New probes count from the next benchmark version, after a 7-day notice in an issue.

**Adding a column** to the tables takes one line in `src/sandbox_bench/boards.py`: the metric and the probe that must pass to be shown.
