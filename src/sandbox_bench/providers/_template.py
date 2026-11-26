"""Copy me: ``cp _template.py <you>.py``, rename the class, then fill in each method.

The registry skips this file (leading underscore). Your copy is picked up automatically by
name: ``sbx validate <you>``, then ``sbx check <you>``.

Rules (CONTRIBUTING, "Adapter rules"):
- Public SDK or REST API only, with the SDK version pinned in ``pyproject.toml``.
- Map, don't optimise: no retries, pre-warming or caching. The harness does all timing,
  timeouts, pacing and cleanup.
- Name every resource from ``spec.name`` (snapshots from ``name``): the ``sbx-`` prefix is how
  ``reap`` finds leftovers.
- Credentials come from environment variables only, named after the provider (``ACME_*``):
  published runs pass a provider only the secrets with its prefix. Raise ``AccountError`` for
  problems on our side (missing or expired key, no credits, a plan limit); any other exception
  counts as a provider failure.
- Delete the optional methods you don't offer. Each probe you list in ``offers`` needs the
  operations in ``benchmark.REQUIRES``; ``sbx validate`` checks that.
"""

from __future__ import annotations

import os
from collections.abc import Mapping, Sequence
from typing import ClassVar

import httpx

from sandbox_bench.adapter import AccountError, Adapter, Endpoint, ExecResult, Spec


class Acme(Adapter[str, str]):
    """Handles are whatever identifies a sandbox or snapshot for you; here, id strings."""

    name = "acme"  # must match the file name: providers/acme.py
    product = "microvm"  # shown as "Acme (microvm)"
    owner = "@your-github-handle"
    access = "rest"  # or "sdk"
    plan = "free tier"
    region = "us-east-1"  # your region nearest the us-east runner
    start_mode = "cold"  # pool | memory | cold
    sdk = ""  # e.g. "acme==1.2.3"; empty for plain REST
    offers: ClassVar[Mapping[str, str]] = {}
    """Every probe your public docs claim, each with the docs link that claims it, e.g.
    ``{"pause-keeps-memory": "https://docs.acme.dev/pause"}``. create-exec and file-roundtrip
    are always tested and need no entry."""
    mechanisms: ClassVar[Mapping[str, str]] = {}
    """How a non-native operation works, e.g. ``{"fork": "snapshot, then create copies"}``."""
    pacing_s = 0.0  # minimum gap between calls, only for a documented rate limit

    def __init__(self) -> None:
        key = os.environ.get("ACME_API_KEY")
        if not key:
            raise AccountError("set ACME_API_KEY")
        self.http = httpx.Client(
            base_url="https://api.acme.dev/v1", headers={"Authorization": f"Bearer {key}"}
        )

    def close(self) -> None:
        """Optional: called once at the end of a run."""
        self.http.close()

    # ---- required ----------------------------------------------------------------------------
    def create(self, spec: Spec) -> str:
        """Create ``spec.name`` from the default image at ``spec.size``; deny outbound traffic
        when ``spec.egress`` is False. Return once your API says it's created; the harness
        then times until a command succeeds inside."""
        raise NotImplementedError

    def exec(self, sb: str, cmd: str, timeout_s: float) -> ExecResult:
        """Run ``sh -c cmd``. A non-zero exit is a result, not an exception."""
        raise NotImplementedError

    def destroy(self, sb: str) -> None:
        """Delete the sandbox; don't raise if it's already gone."""
        raise NotImplementedError

    # ---- optional: keep what you offer -------------------------------------------------------
    def pause(self, sb: str) -> None:
        raise NotImplementedError

    def resume(self, sb: str) -> None:
        """Return when your API says it's running. Poll with ``self.wait_until(...)``."""
        raise NotImplementedError

    def snapshot(self, sb: str, name: str) -> str:
        """Snapshot a running sandbox as ``name``; return once the snapshot is usable."""
        raise NotImplementedError

    def restore(self, snap: str, spec: Spec) -> str:
        """Create a new sandbox ``spec.name`` from the snapshot."""
        raise NotImplementedError

    def delete_snapshot(self, snap: str) -> None:
        raise NotImplementedError

    def fork(self, sb: str, specs: Sequence[Spec]) -> list[str]:
        """One copy of the running sandbox per spec, in order. Any public mechanism counts."""
        raise NotImplementedError

    def expose_port(self, sb: str, port: int) -> Endpoint:
        """A URL the runner can GET, plus any headers it needs (e.g. a preview token)."""
        raise NotImplementedError

    def ping(self) -> None:
        """The cheapest authenticated call, e.g. listing sandboxes. Timed as API RTT."""
        raise NotImplementedError

    def reap(self, prefix: str) -> int:
        """Delete every sandbox and snapshot whose name starts with ``prefix``; return how
        many. Never touch anything else."""
        raise NotImplementedError
