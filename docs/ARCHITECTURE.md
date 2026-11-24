# Architecture (proposed for v0.1)

The design goal is that **adding a provider means adding one folder, and adding a benchmark means adding one folder**, while the core harness stays small and owned by maintainers.

## Stack decision

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
│   ├── adapter.py              #   Adapter protocol + Capabilities enum
│   ├── timing.py               #   monotonic timers, "ready" probe
│   ├── runner.py               #   interleaved scheduler, timeouts, retries=0
│   ├── checks.py               #   fs/memory/process/fork correctness helpers
│   ├── reaper.py               #   tag-based cleanup of leaked sandboxes
│   ├── stats.py                #   percentiles, bootstrap CI, rank bands
│   ├── schema.py               #   pydantic models for results (source of truth)
│   └── cli.py                  #   `sbx run|list|report|probe`
├── providers/
│   └── e2b/
│       ├── provider.yaml       #   configs, capabilities, plan, SDK pin, ToS note
│       ├── adapter.py          #   thin mapping to the native SDK
│       └── README.md
├── benchmarks/
│   └── state/pause_resume/
│       ├── benchmark.yaml      #   track, requires: [pause_resume], metrics, n
│       └── bench.py            #   scenario using only the Adapter protocol
├── images/base/Dockerfile      # standard image
├── pricing/pricing.yaml        # dated, sourced list prices
├── results/
│   └── 2026-12-01/<run_id>/
│       ├── manifest.json       #   harness ver, git sha, runner region/spec, SDK versions
│       ├── samples.jsonl       #   one line per sample (raw)
│       └── summary.json        #   aggregated per config × metric
├── site/                       # Astro static site
├── docs/                       # vision, methodology, governance, RFCs, disputes
└── .github/workflows/          # lint/test on PR; scheduled runs on main only
```

## Core interfaces (sketch)

```python
class Capability(StrEnum):
    FS_SNAPSHOT = "fs_snapshot"; MEMORY_SNAPSHOT = "memory_snapshot"
    PAUSE_RESUME = "pause_resume"; LIVE_FORK = "live_fork"
    CUSTOM_IMAGE = "custom_image"; PREVIEW_URL = "preview_url"
    EGRESS_POLICY = "egress_policy"; GPU = "gpu"; DESKTOP = "desktop"
    # ...

class Sandbox(Protocol):
    id: str
    async def exec(self, cmd: str, timeout_s: float) -> ExecResult: ...
    async def write_file(self, path: str, data: bytes) -> None: ...
    async def read_file(self, path: str) -> bytes: ...

class Adapter(Protocol):
    name: str
    capabilities: frozenset[Capability]
    async def create(self, spec: SandboxSpec) -> Sandbox: ...
    async def destroy(self, sb: Sandbox) -> None: ...
    # Optional, gated by capabilities. Raises NotSupported otherwise.
    async def snapshot(self, sb: Sandbox) -> SnapshotRef: ...
    async def restore(self, ref: SnapshotRef, spec: SandboxSpec) -> Sandbox: ...
    async def pause(self, sb: Sandbox) -> None: ...
    async def resume(self, sb: Sandbox) -> Sandbox: ...
    async def fork(self, sb: Sandbox, n: int) -> list[Sandbox]: ...
    async def list_tagged(self, tag: str) -> list[str]: ...   # for the reaper
```

A benchmark only ever sees `Adapter` and `Sandbox`. The **harness takes the timestamps around adapter calls** and runs the "ready" probe itself, so an adapter can't change what gets timed. Adapters must not retry, pre-warm or cache. Reviewers enforce this, and a lint test fails if an adapter imports `time` or `asyncio.sleep`.

## Result sample schema (one JSONL line)

```json
{
  "run_id": "2026-12-01T06-00Z-useast",
  "harness_version": "0.1.0",
  "benchmark": "state/pause-resume",
  "config": "e2b/default/pro/us-east/2c4g",
  "division": "default",
  "iteration": 7, "warmup": false,
  "metric": "resume_ready_ms", "value": 412.8, "unit": "ms",
  "ok": true, "error_class": null, "error_detail": null,
  "checks": {"memory_preserved": true, "fs_preserved": true, "process_preserved": true},
  "sdk": {"name": "e2b", "version": "x.y.z"},
  "client_region": "us-east-1", "ts": "2026-12-01T06:03:12.481Z"
}
```

`schema.py` is the source of truth. A JSON Schema is exported from it for the website and for other consumers.

## Execution infrastructure

- **Runner:** a small dedicated VM in a fixed region (e.g. AWS us-east-1), registered as an **ephemeral** GitHub Actions self-hosted runner.
- **Never runs untrusted code.** The scheduled workflow triggers only on `schedule` and `workflow_dispatch` from `main`. Pull requests run unit tests on GitHub-hosted runners, with no provider secrets and a mock adapter.
- **Publishing:** after a run, a bot opens a PR that adds `results/<date>/<run_id>/`. CI validates the schema and rebuilds the site preview. The PR is auto-merged if validation passes, so the merge history doubles as an audit log.
- **Secrets:** one API key per provider in GitHub Actions environment secrets, scoped to the `bench` environment.
- **Budget guard:** each adapter declares an estimated cost per iteration, and the runner refuses to start if the projected monthly spend exceeds the limit in `budget.yaml`.

## Extensibility checklists

**Add a provider:**
1. Copy `providers/_template/`.
2. Fill in `provider.yaml`, including the ToS check.
3. Implement `create`, `exec` and `destroy`, plus any optional operations you claim.
4. Run `sbx probe <provider>` locally.
5. Open a PR.

**Add a benchmark:**
1. Copy `benchmarks/_template/`.
2. Declare `requires:` capabilities and metrics, including timing boundaries in the glossary format.
3. Write `bench.py` against the Adapter protocol.
4. Add a mock-adapter test.
5. Open a PR. A new *track* needs an RFC.
