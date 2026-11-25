# Architecture (proposed for v0.1)

The design goal is that **adding a provider, a probe or a board each means adding one folder**, while the core harness stays small and owned by maintainers. Probes follow the Terminal-Bench/Harbor pattern: each one is a self-contained directory with an action and a verifier.

## Stack

**Python 3.12, managed with `uv`.** Why Python:

- Every major provider ships a Python SDK (E2B, Daytona, Modal, Tensorlake, Vercel, Blaxel, Morph, Beam).
- Harbor, which we use for the Terminal-Bench workload, is Python.
- The analysis tools (pandas/polars, scipy bootstrap) are first-class in Python.

**TypeScript-only providers** (Freestyle, Cloudflare Sandbox, which runs inside a Worker) are supported through an out-of-process adapter that speaks the same interface as line-delimited JSON over stdio (`adapters/_bridge/`). Timing still happens in the Python harness, and the bridge's own overhead is measured with a no-op call and reported. This can wait until after v0.1 if those providers are not in the launch set.

**Website:** a static site built with Astro from `results/`, deployed to GitHub Pages or Cloudflare Pages. There is no backend. "View raw data" links point straight to files in the repo.

## Repository layout

```
sandbox-bench/
├── src/sandbox_bench/          # core harness (maintainer-owned)
│   ├── adapter.py              #   Adapter + Sandbox protocols, NotSupported
│   ├── timing.py               #   monotonic timers, "ready" check, start-mode detection
│   ├── runner.py               #   interleaved scheduler, one op in flight, timeouts
│   ├── reaper.py               #   tag-based cleanup of leaked sandboxes
│   ├── scoring.py              #   probe pass rates, category means, probe score
│   ├── stats.py                #   percentiles, bootstrap CI, rank bands
│   ├── schema.py               #   pydantic models for results (source of truth)
│   └── cli.py                  #   `sbx run|probe|report|submit`
├── providers/
│   └── e2b/
│       ├── provider.yaml       #   configs, supported probes, start mode, plan, SDK pin, ToS note
│       ├── adapter.py          #   thin mapping to the native SDK
│       └── README.md
├── probes/                     # the suite: one folder per probe
│   └── state/pause-keeps-memory/
│       ├── probe.yaml          #   category, description, attempts, suite version
│       └── probe.py            #   setup → action → verifier, via the Adapter protocol only
├── boards/                     # performance boards: one folder per board
│   └── resume/
│       ├── board.yaml          #   metrics, gate probe, n, clock boundaries
│       └── board.py
├── helper/                     # sbx-helper (Go): hold/inspect/mark/check/toolset-check/start-age
├── toolset/
│   ├── v1.yaml                 #   pinned versions (the spec)
│   ├── Dockerfile              #   reference implementation
│   └── setup.sh                #   reference implementation for snapshot-based providers
├── pricing/pricing.yaml        # dated, sourced list prices
├── results/
│   └── 2026-12-01/<run_id>/
│       ├── manifest.json       #   harness + suite version, git sha, runner, SDK versions
│       ├── samples.jsonl       #   one line per probe attempt or metric sample (raw)
│       └── summary.json        #   probe scores + board aggregates per configuration
├── site/                       # Astro static site
├── docs/                       # vision, methodology, governance, RFCs
└── .github/workflows/          # lint/test on PR; scheduled runs on main only
```

## Core interfaces (sketch)

```python
class Env(StrEnum):
    DEFAULT = "default"          # provider's out-of-the-box environment
    TOOLSET = "toolset"          # pinned toolset, built the provider's native way

class Sandbox(Protocol):
    id: str
    async def exec(self, cmd: str, timeout_s: float) -> ExecResult: ...
    async def write_file(self, path: str, data: bytes) -> None: ...
    async def read_file(self, path: str) -> bytes: ...

class Adapter(Protocol):
    name: str
    async def create(self, spec: SandboxSpec, env: Env = Env.DEFAULT) -> Sandbox: ...
    async def destroy(self, sb: Sandbox) -> None: ...
    async def list_tagged(self, tag: str) -> list[str]: ...          # for the reaper
    # Optional. Raise NotSupported if the provider lacks the feature (probe shows "—").
    async def prepare_toolset(self, toolset: Toolset) -> None: ...   # one-time, timed separately
    async def build_from_dockerfile(self, dockerfile: Path) -> EnvRef: ...
    async def snapshot(self, sb: Sandbox) -> SnapshotRef: ...
    async def restore(self, ref: SnapshotRef, spec: SandboxSpec) -> Sandbox: ...
    async def pause(self, sb: Sandbox) -> None: ...
    async def resume(self, sb: Sandbox) -> Sandbox: ...
    async def fork(self, sb: Sandbox, n: int) -> list[Sandbox]: ...
    async def set_egress(self, sb: Sandbox, allow: bool) -> None: ...
    async def expose_port(self, sb: Sandbox, port: int) -> str: ...  # returns a reachable URL
```

Probes and boards only ever see `Adapter` and `Sandbox`. The **harness takes the timestamps around adapter calls**, runs the "ready" check and uploads `sbx-helper`, so an adapter can't change what gets timed or verified. Adapters must not retry, pre-warm or cache. Reviewers enforce this, and a lint test fails if an adapter imports `time` or `asyncio.sleep`.

A probe is a small async function:

```python
async def run(adapter: Adapter, h: Harness) -> Verdict:
    sb = await h.create(adapter)                 # timed + ready-checked by the harness
    await h.helper(sb, "hold")                   # start the memory holder
    before = await h.helper(sb, "inspect")
    await h.call(adapter.pause, sb)
    sb = await h.call(adapter.resume, sb)
    after = await h.helper(sb, "inspect")
    return Verdict.check(after.pid == before.pid and after.hash == before.hash
                         and after.counter > before.counter)
```

## Result sample schema (one JSONL line)

```json
{
  "run_id": "2026-12-01T06-00Z-useast",
  "harness_version": "0.1.0", "suite": "core-v0.1",
  "config": "e2b/default/pro/us-east/2c4g", "division": "default",
  "kind": "metric", "board": "resume", "metric": "resume_ms",
  "iteration": 7, "warmup": false, "value": 412.8, "unit": "ms",
  "ok": true, "error_class": null, "start_mode": "warm",
  "sdk": {"name": "e2b", "version": "x.y.z"},
  "client_region": "us-east-1", "ts": "2026-12-01T06:03:12.481Z"
}
```

Probe attempts use `"kind": "probe"`, plus `"probe": "state/pause-keeps-memory"`, `"outcome": "pass" | "fail" | "unsupported"` and the verifier's evidence (e.g. PIDs and hashes before and after). `schema.py` is the source of truth. A JSON Schema is exported from it for the website and for other consumers.

## Execution infrastructure

- **Runner:**
  - **Development:** any local machine runs `sbx run`.
  - **Published results (from week 3):** a fixed machine in a declared region, registered as an **ephemeral** GitHub Actions self-hosted runner.
- **Never runs untrusted code.** The scheduled workflow triggers only on `schedule` and `workflow_dispatch` from `main`. Pull requests run unit tests on GitHub-hosted runners, with no provider secrets and a mock adapter.
- **Publishing:** after a run, a bot opens a PR that adds `results/<date>/<run_id>/`. CI validates the schema and rebuilds the site preview. The PR is auto-merged if validation passes, so the merge history doubles as an audit log.
- **Secrets:** one API key per provider in GitHub Actions environment secrets, scoped to the `bench` environment.
- **Budget guard:** each adapter declares an estimated cost per iteration, and the runner refuses to start if the projected monthly spend exceeds the limit in `budget.yaml`.

## Extensibility checklists

**Add a provider:**
1. Copy `providers/_template/`.
2. Fill in `provider.yaml`: configurations, supported probes, start mode, and the ToS check.
3. Implement `create`, `exec` and `destroy`, plus any optional operations you support.
4. Run `sbx probe <provider>` locally.
5. Open a PR.

**Add a probe:**
1. Copy `probes/_template/` into a category.
2. Describe the pass condition in one sentence.
3. Write `probe.py`: setup → action → verifier. Use the Adapter protocol only, and `sbx-helper` for any in-sandbox checks.
4. Add a mock-adapter test for both pass and fail.
5. Open a PR. New probes ship in the next suite version. A new *category* needs an RFC.

**Add a board:**
1. Copy `boards/_template/`.
2. Declare the metrics, the clock boundaries (in the METHODOLOGY format) and the gating probe.
3. Write `board.py`.
4. Add a mock-adapter test.
5. Open a PR.
