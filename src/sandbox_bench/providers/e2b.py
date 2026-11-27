"""E2B sandboxes (Firecracker microVMs), through the ``e2b`` Python SDK.

Credentials come from the environment: ``E2B_API_KEY`` (the SDK reads it itself).

Notes for readers of the results:

- **Size.** E2B fixes CPU and memory when a template is built. The default ``base`` template
  gives 2 vCPU / 512 MiB, and choosing a size at create needs "resizable templates", which our
  project doesn't have (``400: Resizable templates are not enabled for your team``, 2026-11-27).
  So sandboxes start from ``TEMPLATE``: E2B's own base image, built once on the account at
  2 vCPU / 4 GiB with nothing added. ``python -m sandbox_bench.providers.e2b
  build-template`` builds it (about 25 s). ADR-0011.
- **Names.** Sandboxes take no name, so ``spec.name`` goes into their metadata. A fork inherits
  its parent's metadata, so forks carry the parent's name, which has the same run prefix: the
  reaper finds them. Snapshots are named, as ``<team>/<name>``.
- Every sandbox gets a lifetime of ``TTL_S``, after which E2B kills it, so one leaked by a
  crashed run deletes itself.
- **Ports.** Public URLs on projects created since 2026-10-30 need the sandbox's traffic access
  token; the endpoint carries it as a header. This is E2B's default setting, left as it is.
- **No retries.** The SDK retries 429/502/503/504 responses and failed connections by default.
  Both are turned off (``retries=0`` on every call, ``E2B_CONNECTION_RETRIES=0``): the adapter
  rules allow no retries, and throttling counts as the provider's failure (ADR-0009).
- **Exec.** The SDK runs commands through a login bash by default; the adapter passes
  ``shell=["/bin/sh", "-c"]`` so a command runs under ``sh -c`` as everywhere else. A non-zero
  exit raises ``CommandExitException`` in the SDK and is turned back into a result here.
"""

from __future__ import annotations

import os
import sys
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from typing import Final

# Read once, when the SDK is imported: no retried connects (see the module docstring).
os.environ.setdefault("E2B_CONNECTION_RETRIES", "0")

from e2b import (
    AuthenticationException,
    CommandExitException,
    Sandbox,
    SandboxException,
    SandboxQuery,
    SandboxState,
    Template,
)

from sandbox_bench.adapter import (
    RESOURCE_PREFIX,
    AccountError,
    Adapter,
    Endpoint,
    ExecResult,
    Size,
    Spec,
)

TEMPLATE: Final = "sandbox-bench-2c4g"
"""E2B's base image (``e2bdev/base``) at 2 vCPU / 4 GiB. Not named ``sbx-``: it is a fixture
kept on the account, never reaped. ADR-0011."""
TEMPLATE_CPU: Final = 2
TEMPLATE_MEMORY_MB: Final = 4096
TTL_S: Final = 60 * 60
"""Sandbox lifetime: longer than any attempt (snapshot timeout 15 min, plus restore and
checks), and the most a Hobby project allows."""
LABEL: Final = {"created-by": "sandbox-bench"}
TOKEN_HEADER: Final = "e2b-traffic-access-token"  # noqa: S105 - a header name
SH: Final = ("/bin/sh", "-c")
NO_RETRIES: Final = 0

DOCS: Final = "https://docs.e2b.dev"
PORT_DOCS: Final = f"{DOCS}/network/public-url#connecting-to-a-server-running-inside-the-sandbox"

_ACCOUNT_STATUS: Final = frozenset({401, 402, 403})
_ACCOUNT_WORDS: Final = ("credit", "billing", "quota", "payment")
_PLAN_LIMIT_WORDS: Final = ("concurrent", "maximum number", *_ACCOUNT_WORDS)


def _is_account_error(exc: Exception) -> bool:
    """Whether an E2B error is about our account (auth, credits, a plan limit)."""
    if isinstance(exc, AuthenticationException):
        return True
    status = getattr(exc, "status_code", None)
    message = str(exc).lower()
    if status == 429:  # throttled is theirs (ADR-0009); the concurrency limit is our plan's
        return any(word in message for word in _PLAN_LIMIT_WORDS)
    return status in _ACCOUNT_STATUS or any(word in message for word in _ACCOUNT_WORDS)


@contextmanager
def _account_errors() -> Iterator[None]:
    """Re-raise account-side E2B errors as ``AccountError``; let the rest through."""
    try:
        yield
    except (SandboxException, AuthenticationException) as exc:
        if _is_account_error(exc):
            raise AccountError(str(exc)) from exc
        raise


class E2B(Adapter[Sandbox, str]):
    """E2B sandboxes. A snapshot handle is its id, ``<team>/<name>:default``."""

    name = "e2b"
    product = "microvm"
    owner = "@sandboxrouting"
    access = "sdk"
    plan = "Hobby (free, $100 one-time credit)"
    region = "us-west-1 (the default; us-east-1 isn't self-serve)"
    start_mode = "memory"
    size = Size(vcpu=TEMPLATE_CPU, memory_gib=TEMPLATE_MEMORY_MB / 1024)
    sdk = "e2b==2.66.0"

    offers = {  # noqa: RUF012 - ClassVar mapping declared on the base class
        "create-exec": f"{DOCS}/commands",
        "file-roundtrip": f"{DOCS}/filesystem/read-write",
        "internet": f"{DOCS}/network/internet-access#controlling-internet-access",
        "egress-block": f"{DOCS}/network/internet-access#controlling-internet-access",
        "exposed-port": PORT_DOCS,
        "pause-keeps-files": f"{DOCS}/sandbox/persistence#pausing-sandbox",
        "pause-keeps-memory": f"{DOCS}/sandbox/persistence#pausing-sandbox",
        "snapshot-keeps-files": f"{DOCS}/sandbox/snapshots#create-a-sandbox-from-a-snapshot",
        "snapshot-keeps-memory": f"{DOCS}/sandbox/snapshots#create-a-sandbox-from-a-snapshot",
        "fork-keeps-memory": f"{DOCS}/sandbox/fork",
        "fork-isolation-x3": f"{DOCS}/sandbox/fork",
    }
    # Pacing stays 0: Hobby allows 1 create/s and 10 list calls/s per endpoint
    # (https://docs.e2b.dev/billing#api-rate-limits), and with one operation in flight the
    # harness never comes close; each create waits for a command to succeed before the next.

    def __init__(self, sdk: type[Sandbox] = Sandbox) -> None:
        if sdk is Sandbox and not os.environ.get("E2B_API_KEY"):
            msg = "E2B_API_KEY is not set; create a key at https://e2b.dev/dashboard"
            raise AccountError(msg)
        self._sdk = sdk

    # ---- required ----------------------------------------------------------------------------
    def create(self, spec: Spec) -> Sandbox:
        return self._create(spec, TEMPLATE)  # ADR-0011

    def exec(self, sb: Sandbox, cmd: str, timeout_s: float) -> ExecResult:
        with _account_errors():
            try:
                result = sb.commands.run(cmd, shell=SH, timeout=timeout_s)
            except CommandExitException as exc:
                return ExecResult(exc.exit_code, exc.stdout, exc.stderr)
        return ExecResult(result.exit_code, result.stdout, result.stderr)

    def destroy(self, sb: Sandbox) -> None:
        with _account_errors():
            sb.kill(retries=NO_RETRIES)  # False, not an error, when it's already gone

    # ---- pause / resume ----------------------------------------------------------------------
    def pause(self, sb: Sandbox) -> None:
        with _account_errors():
            sb.pause(retries=NO_RETRIES)

    def resume(self, sb: Sandbox) -> None:
        with _account_errors():
            sb.connect(timeout=TTL_S, retries=NO_RETRIES)  # connecting resumes a paused sandbox

    # ---- snapshots ---------------------------------------------------------------------------
    def snapshot(self, sb: Sandbox, name: str) -> str:
        with _account_errors():  # returns once sandboxes can be created from it
            return sb.create_snapshot(name=name, retries=NO_RETRIES).snapshot_id

    def restore(self, snap: str, spec: Spec) -> Sandbox:
        return self._create(spec, snap)

    def delete_snapshot(self, snap: str) -> None:
        with _account_errors():
            self._sdk.delete_snapshot(snap, retries=NO_RETRIES)

    def fork(self, sb: Sandbox, specs: Sequence[Spec]) -> list[Sandbox]:
        if not specs:
            return []
        with _account_errors():
            results = sb.fork(count=len(specs), timeout=TTL_S, retries=NO_RETRIES)
        children = [r for r in results if not isinstance(r, Exception)]
        failed = [r for r in results if isinstance(r, Exception)]
        if failed:  # each fork fails on its own; one failure fails the operation
            for child in children:
                child.kill(retries=NO_RETRIES)
            with _account_errors():
                raise failed[0]
        return children

    # ---- network -----------------------------------------------------------------------------
    def expose_port(self, sb: Sandbox, port: int) -> Endpoint:
        token = sb.traffic_access_token  # None when the sandbox is public
        headers = {TOKEN_HEADER: token} if token else {}
        return Endpoint(url=f"https://{sb.get_host(port)}/", headers=headers)

    # ---- account -----------------------------------------------------------------------------
    def ping(self) -> None:
        with _account_errors():
            self._sdk.list(limit=1, retries=NO_RETRIES).next_items()

    def reap(self, prefix: str) -> int:
        if not prefix.startswith(RESOURCE_PREFIX):
            msg = f"refusing to reap with prefix {prefix!r}: must start with {RESOURCE_PREFIX!r}"
            raise ValueError(msg)
        deleted = 0
        with _account_errors():
            for sandbox_id in self._own_sandboxes(prefix):
                deleted += bool(self._sdk.kill(sandbox_id, retries=NO_RETRIES))
            for snap in self._own_snapshots(prefix):
                deleted += bool(self._sdk.delete_snapshot(snap, retries=NO_RETRIES))
        return deleted

    # ---- helpers -------------------------------------------------------------------------------
    def _create(self, spec: Spec, template: str) -> Sandbox:
        try:
            with _account_errors():
                return self._sdk.create(
                    template,
                    timeout=TTL_S,
                    metadata={**LABEL, "name": spec.name},
                    allow_internet_access=spec.egress,
                    retries=NO_RETRIES,
                )
        except SandboxException as exc:
            if template == TEMPLATE and "not found" in str(exc).lower():
                msg = f"template {TEMPLATE} is missing: run `{BUILD_COMMAND}` once"
                raise AccountError(msg) from exc
            raise

    def _own_sandboxes(self, prefix: str) -> list[str]:
        """Ids of running or paused sandboxes this harness created, named ``prefix*``."""
        query = SandboxQuery(
            metadata=dict(LABEL), state=[SandboxState.RUNNING, SandboxState.PAUSED]
        )
        pages = self._sdk.list(query=query, limit=100, retries=NO_RETRIES)
        found: list[str] = []
        while pages.has_next:
            found += [
                s.sandbox_id
                for s in pages.next_items()
                if s.metadata.get("name", "").startswith(prefix)
            ]
        return found

    def _own_snapshots(self, prefix: str) -> list[str]:
        """Ids of snapshots named ``prefix*`` (names come back as ``<team>/<name>``)."""
        pages = self._sdk.list_snapshots(limit=100, retries=NO_RETRIES)
        found: list[str] = []
        while pages.has_next:
            found += [
                s.snapshot_id
                for s in pages.next_items()
                if any(n.rsplit("/", 1)[-1].startswith(prefix) for n in s.names)
            ]
        return found


BUILD_COMMAND: Final = "uv run python -m sandbox_bench.providers.e2b build-template"


def build_template() -> str:
    """Build ``TEMPLATE`` from E2B's base image at the standard size; return its id."""
    builder = Template().from_base_image()
    with _account_errors():
        info = Template.build(
            builder, TEMPLATE, cpu_count=TEMPLATE_CPU, memory_mb=TEMPLATE_MEMORY_MB
        )
    return info.template_id


if __name__ == "__main__":  # pragma: no cover - a one-time setup step, run by hand
    if sys.argv[1:] != ["build-template"]:
        sys.exit(f"usage: {BUILD_COMMAND}")
    sys.stdout.write(f"built {TEMPLATE}: {build_template()}\n")
