"""Daytona, default (container) sandbox class, through the v0 Python SDK.

Credentials come from the environment: ``DAYTONA_API_KEY`` and ``DAYTONA_API_URL`` (the SDK
reads them itself). The account's key is a v0 key, hence ``Daytona().v0``.

Notes for readers of the results:

- ``exec`` returns stdout and stderr merged into ``stdout``: the SDK's ``process.exec`` gives
  one combined output stream, so ``stderr`` is always empty.
- Sandboxes are created from the built-in ``daytona-medium`` snapshot (2 vCPU / 4 GiB / 8 GiB
  disk); the SDK's no-argument create gives only 1 vCPU / 1 GiB.
- Snapshots of a container sandbox capture the filesystem only, so only
  ``snapshot-keeps-files`` is offered. Pause and fork are documented for the VM class only.
- Every sandbox gets a wall-clock TTL, so one leaked by a crashed run deletes itself.
- With ``network_block_all`` a TCP handshake to any address still completes (a sinkhole), but
  no data comes back and DNS returns no answers; only a real request shows the block.
- The SDK keeps HTTP connections to the sandbox proxy alive, but the proxy drops them after
  about 5 idle minutes and the SDK's next command on one fails with a connection reset. So
  after ``STALE_AFTER_S`` without a command, create and restore start from a new SDK client
  (3.5 ms, no network): nothing is retried, the new sandbox just doesn't inherit dead
  connections. A sandbox created *before* such a gap keeps the old client and can still hit one.
  See docs/decisions/0002-daytona-fresh-client-after-idle.md.
"""

from __future__ import annotations

import math
import shlex
import time
from collections.abc import Iterator
from contextlib import contextmanager
from typing import TYPE_CHECKING, Final

from daytona import Daytona, DaytonaError, DaytonaNotFoundError
from daytona.v0 import CreateSandboxFromSnapshotParams
from daytona_api_client import SandboxState, SnapshotState

from sandbox_bench.adapter import (
    RESOURCE_PREFIX,
    AccountError,
    Adapter,
    Endpoint,
    ExecResult,
    Size,
    Spec,
)
from sandbox_bench.benchmark import TIMEOUTS

if TYPE_CHECKING:
    from daytona import DaytonaV0Client
    from daytona.v0 import Sandbox

SNAPSHOT: Final = "daytona-medium"
"""Built-in snapshot that gives the standard 2 vCPU / 4 GiB."""
TARGET: Final = "us"
AUTO_STOP_MIN: Final = 15
"""Stop a sandbox after this many idle minutes (Daytona's own default, set explicitly)."""
TTL_MIN: Final = 60
"""Destroy a sandbox this long after creation, whatever its state: covers leaks from a
crashed run. Longer than any attempt (snapshot timeout 15 min, plus restore and checks)."""
LABELS: Final = {"created-by": "sandbox-bench"}
PREVIEW_TOKEN_HEADER: Final = "X-Daytona-Preview-Token"  # noqa: S105 - a header name
STALE_AFTER_S: Final = 240.0
"""Idle time after which the proxy may have closed the SDK's connections (fine at 245 s,
reset at 310 s and 340 s in testing, 2026-11-26)."""

_ACCOUNT_STATUS: Final = frozenset({401, 402, 403, 429})
_ACCOUNT_WORDS: Final = ("quota", "credit", "suspended", "limit exceeded", "billing")
_GONE: Final = frozenset({SandboxState.DESTROYED, SandboxState.DESTROYING})
_SNAPSHOT_FAILED: Final = frozenset({SnapshotState.ERROR, SnapshotState.BUILD_FAILED})

DOCS: Final = "https://www.daytona.io/docs/en"


def _is_account_error(exc: Exception) -> bool:
    """Whether a Daytona API error is about our account (auth, plan, credits, quota)."""
    if getattr(exc, "source", None) == "daemon":  # raised inside the sandbox, not by the API
        return False
    status = getattr(exc, "status_code", None)
    message = str(exc).lower()
    return status in _ACCOUNT_STATUS or any(word in message for word in _ACCOUNT_WORDS)


@contextmanager
def _account_errors() -> Iterator[None]:
    """Re-raise account-side Daytona errors as ``AccountError``; let the rest through."""
    try:
        yield
    except DaytonaError as exc:
        if _is_account_error(exc):
            raise AccountError(str(exc)) from exc
        raise


class DaytonaContainer(Adapter["Sandbox", str]):
    """Daytona container sandboxes. A snapshot handle is the snapshot's name."""

    name = "daytona"
    product = "container"
    owner = "@sandboxrouting"
    access = "sdk"
    plan = "pay-as-you-go"  # no free plan; billed per second against credits. ADR-0006
    region = TARGET
    start_mode = "pool"
    size = Size(vcpu=2, memory_gib=4)
    sdk = "daytona==2.2.0"

    offers = {  # noqa: RUF012 - ClassVar mapping declared on the base class
        "create-exec": f"{DOCS}/process-code-execution.md",
        "file-roundtrip": f"{DOCS}/file-system-operations.md",
        "internet": f"{DOCS}/network-limits.md",
        "egress-block": f"{DOCS}/network-limits.md",
        "exposed-port": f"{DOCS}/preview.md",
        "snapshot-keeps-files": f"{DOCS}/snapshots.md#create-snapshot-from-sandbox",
    }

    def __init__(self, client: DaytonaV0Client | None = None) -> None:
        self._sdk = client
        self._own_sdk = client is None  # an injected client (tests) is never replaced
        self._last_command = time.monotonic()

    @property
    def _client(self) -> DaytonaV0Client:
        """The SDK client, built on first use so the adapter can be inspected without keys."""
        if self._sdk is None:
            try:
                self._sdk = Daytona().v0
            except DaytonaError as exc:  # missing or malformed credentials
                raise AccountError(f"Daytona client: {exc}") from exc
        return self._sdk

    # ---- required ----------------------------------------------------------------------------
    def create(self, spec: Spec) -> Sandbox:
        return self._create(spec, snapshot=SNAPSHOT, timeout_s=TIMEOUTS["create"])

    def exec(self, sb: Sandbox, cmd: str, timeout_s: float) -> ExecResult:
        with _account_errors():
            response = sb.process.exec(f"sh -c {shlex.quote(cmd)}", timeout=math.ceil(timeout_s))
        self._last_command = time.monotonic()
        # Daytona merges the command's stdout and stderr into one stream.
        return ExecResult(exit_code=response.exit_code, stdout=response.result)

    def destroy(self, sb: Sandbox) -> None:
        with _account_errors():
            try:
                # Deletion is asynchronous; wait so a destroyed sandbox no longer holds quota.
                sb.delete(timeout=TIMEOUTS["destroy"], wait=True)
            except DaytonaNotFoundError:
                return

    # ---- snapshots (files only for containers) -----------------------------------------------
    def snapshot(self, sb: Sandbox, name: str) -> str:
        deadline = time.monotonic() + TIMEOUTS["snapshot"]
        with _account_errors():
            # Returns once the sandbox has left the "snapshotting" state ...
            sb.create_snapshot(name, timeout=TIMEOUTS["snapshot"])
        # ... but the snapshot itself may still be processing: wait until it is usable.
        self.wait_until(
            lambda: self._snapshot_active(name),
            timeout_s=max(deadline - time.monotonic(), 0),
            interval_s=2,
            what=f"snapshot {name} to become active",
        )
        return name

    def restore(self, snap: str, spec: Spec) -> Sandbox:
        return self._create(spec, snapshot=snap, timeout_s=TIMEOUTS["restore"])

    def delete_snapshot(self, snap: str) -> None:
        with _account_errors():
            try:
                self._client.snapshot.delete(snap)
            except DaytonaNotFoundError:
                return

    # ---- other optional operations -------------------------------------------------------------
    def expose_port(self, sb: Sandbox, port: int) -> Endpoint:
        with _account_errors():
            link = sb.get_preview_link(port, request_timeout=TIMEOUTS["expose_port"])
        # Private sandboxes (the default) need the preview token on every request.
        headers = {} if sb.public or not link.token else {PREVIEW_TOKEN_HEADER: link.token}
        return Endpoint(url=link.url, headers=headers)

    def ping(self) -> None:
        with _account_errors():
            self._client.snapshot.list(page=1, limit=1)

    def reap(self, prefix: str) -> int:
        if not prefix.startswith(RESOURCE_PREFIX):
            msg = f"refusing to reap with prefix {prefix!r}: must start with {RESOURCE_PREFIX!r}"
            raise ValueError(msg)
        deleted = 0
        with _account_errors():
            sandboxes = [
                s for s in self._client.list() if s.name.startswith(prefix) and s.state not in _GONE
            ]
            for sb in sandboxes:
                try:
                    sb.delete(timeout=TIMEOUTS["destroy"])
                except DaytonaNotFoundError:
                    continue
                deleted += 1
            for snap in self._own_snapshots(prefix):
                try:
                    self._client.snapshot.delete(snap)
                except DaytonaNotFoundError:
                    continue
                deleted += 1
        return deleted

    # ---- helpers -------------------------------------------------------------------------------
    def _create(self, spec: Spec, *, snapshot: str, timeout_s: float) -> Sandbox:
        if self._own_sdk and time.monotonic() - self._last_command > STALE_AFTER_S:
            self._sdk = None  # its proxy connections are likely closed: start a new client
        params = CreateSandboxFromSnapshotParams(
            snapshot=snapshot,
            name=spec.name,
            target=TARGET,
            labels=dict(LABELS),
            auto_stop_interval=AUTO_STOP_MIN,
            ttl_minutes=TTL_MIN,
            network_block_all=True if not spec.egress else None,
        )
        with _account_errors():
            return self._client.create(params, timeout=timeout_s)

    def _snapshot_active(self, name: str) -> bool:
        with _account_errors():
            snap = self._client.snapshot.get(name)
        if snap.state in _SNAPSHOT_FAILED:
            msg = f"snapshot {name} failed: {snap.state} {snap.error_reason or ''}".strip()
            raise RuntimeError(msg)
        return bool(snap.state == SnapshotState.ACTIVE)

    def _own_snapshots(self, prefix: str) -> list[str]:
        """Names of the account's non-general snapshots starting with ``prefix``."""
        names: list[str] = []
        page, pages = 1, 1
        while page <= pages:
            listing = self._client.snapshot.list(page=page, limit=100)
            names += [
                s.name
                for s in listing.items
                if s.name.startswith(prefix) and not s.general and s.state != SnapshotState.REMOVING
            ]
            pages = listing.total_pages
            page += 1
        return names
