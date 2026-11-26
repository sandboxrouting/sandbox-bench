"""Freestyle VMs, over the public REST API (``https://api.freestyle.sh/v5``).

Freestyle's SDKs are TypeScript, so this adapter calls the REST API the ``freestyle@0.2.24``
npm SDK uses, with httpx. Spec: ``https://api.freestyle.sh/openapi.json``.

How the operations map:

- Every VM boots from a snapshot (a memory restore); ``freestyle/ubuntu-sm`` is 2 vCPU / 4 GiB.
- The ``firewall`` block is required at create and grants nothing implicitly: one rule allows
  the public Internet, an empty list denies all outbound traffic.
- Pause keeps memory; ``start`` resumes it. A snapshot captures memory and disk.
- There is no native fork: snapshot, then create one VM per copy. The intermediate snapshot
  is deleted when the last copy is destroyed (or right away if the fork fails), so cleanup
  stays outside the fork clock and nothing leaks; the reaper catches it by name otherwise.
- A port is exposed by routing a free ``<name>.style.dev`` domain to it with a TLS rule. The
  rule is deleted with the VM.
"""

from __future__ import annotations

import hashlib
import os
import shlex
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any, ClassVar, Literal

import httpx
from pydantic import BaseModel, ConfigDict

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

API_URL = "https://api.freestyle.sh"
BASE_SNAPSHOT = "freestyle/ubuntu-sm"
EXEC_CAP_S = 300.0
"""Longest exec the API runs inline (``timeoutMs`` ≤ 300000)."""
SLUG_MAX = 63
DOCS = "https://www.freestyle.sh/docs"
SNAPSHOT_DOCS = f"{DOCS}/guides/run-a-minecraft-server-in-a-sandbox#snapshot-the-running-server"
"""'A Freestyle snapshot is a full memory and disk capture, so it preserves the running JVM'."""
BRANCH_DOCS = (
    f"{DOCS}/guides/reverse-engineer-a-binary-with-an-ai-agent"
    "#branch-before-patches-and-destructive-experiments"
)
"""Snapshot, then create a VM per branch; 'keep each hypothesis in a separate branch when the
experiments would interfere'. Implies isolation without stating it: ADR-0005."""

ALLOW_INTERNET: dict[str, Any] = {"action": "allow", "source": {}, "destination": {"public": True}}
"""Inside a create, an endpoint with no identity means the VM being created."""


# ---- response models: only the fields the adapter reads ---------------------------------------
class _Model(BaseModel):
    model_config = ConfigDict(extra="ignore")


VmState = Literal["starting", "running", "pausing", "paused", "stopped"]


class VmData(_Model):
    id: str
    state: VmState
    slug: str | None = None


class VmList(_Model):
    vms: list[VmData]


class ExecResponse(_Model):
    statusCode: int | None = None  # noqa: N815 - API field name
    stdout: str | None = None
    stderr: str | None = None


class SnapshotData(_Model):
    id: str
    slug: str | None = None
    public: bool = False


class SnapshotCreated(_Model):
    snapshotId: str  # noqa: N815 - API field name
    snapshot: SnapshotData


class SnapshotList(_Model):
    snapshots: list[SnapshotData]


class TlsRule(_Model):
    id: str
    domain: str


# ---- handles ----------------------------------------------------------------------------------
@dataclass
class _ForkSource:
    """The snapshot behind a fork, shared by its copies until the last one is destroyed."""

    snapshot: FreestyleSnapshot
    copies: set[str] = field(default_factory=set)


@dataclass(frozen=True, slots=True)
class FreestyleVm:
    id: str
    slug: str
    fork_source: _ForkSource | None = field(default=None, compare=False, repr=False)


@dataclass(frozen=True, slots=True)
class FreestyleSnapshot:
    id: str
    slug: str


class FreestyleApiError(Exception):
    """A non-2xx answer from the Freestyle API that isn't an account problem."""

    def __init__(self, status: int, code: str, message: str, what: str) -> None:
        super().__init__(f"{what}: HTTP {status} {code}: {message}")
        self.status = status
        self.code = code


def derived_name(base: str, suffix: str) -> str:
    """``<base>-<suffix>``, shortened with a stable hash to fit a 63-character slug/label."""
    name = f"{base}-{suffix}"
    if len(name) <= SLUG_MAX:
        return name
    digest = hashlib.sha256(name.encode()).hexdigest()[:8]
    head = base[: SLUG_MAX - len(suffix) - len(digest) - 2].rstrip("-")
    return f"{head}-{digest}-{suffix}"


class Freestyle(Adapter[FreestyleVm, FreestyleSnapshot]):
    name = "freestyle"
    product = "vm"
    owner = "@sandboxrouting"
    access = "rest"
    plan = "free tier"
    region = "not selectable (VMs egress from San Francisco, US)"
    start_mode = "memory"
    size = Size(vcpu=2, memory_gib=4)
    sdk = ""  # REST API v5, as called by the freestyle@0.2.24 npm SDK

    offers: ClassVar[Mapping[str, str]] = {
        "create-exec": f"{DOCS}/vms#create-a-vm",
        "file-roundtrip": f"{DOCS}/vms/files#read-and-write",
        "internet": f"{DOCS}/vms/network/firewall#rules-declared-with-a-vm",
        "egress-block": f"{DOCS}/vms/network/firewall#rules-declared-with-a-vm",
        "exposed-port": f"{DOCS}/vms/domains#free-styledev-names",
        "pause-keeps-files": f"{DOCS}/vms/lifecycle#paused",
        "pause-keeps-memory": f"{DOCS}/vms/lifecycle#paused",
        "snapshot-keeps-files": SNAPSHOT_DOCS,
        "snapshot-keeps-memory": SNAPSHOT_DOCS,
        "fork-keeps-memory": f"{DOCS}/guides/migrate-from-e2b#map-your-current-setup",
        "fork-isolation-x3": BRANCH_DOCS,
    }
    mechanisms: ClassVar[Mapping[str, str]] = {
        "fork": "snapshot, then create N copies",
        "expose_port": "TLS rule routing a free style.dev domain to the port",
    }

    def __init__(
        self,
        api_key: str | None = None,
        *,
        base_url: str = API_URL,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        key = api_key or os.environ.get("FREESTYLE_API_KEY")
        if not key:
            msg = "FREESTYLE_API_KEY is not set; create a key at https://dash.freestyle.sh"
            raise AccountError(msg)
        self._http = httpx.Client(
            base_url=base_url,
            headers={"Authorization": f"Bearer {key}"},
            timeout=httpx.Timeout(60.0, connect=10.0),
            transport=transport,
        )

    def close(self) -> None:
        self._http.close()

    # ---- HTTP -------------------------------------------------------------------------------
    def _call(
        self,
        method: str,
        path: str,
        *,
        json: Mapping[str, Any] | None = None,
        params: Mapping[str, Any] | None = None,
        timeout_s: float | None = None,
        missing_ok: bool = False,
    ) -> httpx.Response:
        """Send one request; raise on failure, except a 404 when ``missing_ok``."""
        timeout = httpx.USE_CLIENT_DEFAULT if timeout_s is None else timeout_s
        response = self._http.request(method, path, json=json, params=params, timeout=timeout)
        if response.is_success or (missing_ok and response.status_code == 404):
            return response
        raise _error(response, f"{method} {path}")

    def _json[M: _Model](self, model: type[M], method: str, path: str, **kw: Any) -> M:
        return model.model_validate_json(self._call(method, path, **kw).content)

    def _vm(self, vm_id: str) -> VmData:
        return self._json(VmData, "GET", f"/v5/vms/{vm_id}")

    def _wait_state(self, data: VmData, state: VmState, timeout_s: float) -> None:
        if data.state == state:
            return
        self.wait_until(
            lambda: self._vm(data.id).state == state,
            timeout_s=timeout_s,
            what=f"VM {data.slug or data.id} to be {state}",
        )

    def _boot(self, spec: Spec, snapshot_id: str, timeout_s: float) -> FreestyleVm:
        body = {
            "snapshotId": snapshot_id,
            "slug": spec.name,
            "firewall": {"rules": [ALLOW_INTERNET] if spec.egress else []},
        }
        data = self._json(VmData, "POST", "/v5/vms", json=body)
        self._wait_state(data, "running", timeout_s)
        return FreestyleVm(id=data.id, slug=spec.name)

    # ---- required ---------------------------------------------------------------------------
    def create(self, spec: Spec) -> FreestyleVm:
        return self._boot(spec, BASE_SNAPSHOT, TIMEOUTS["create"])

    def exec(self, sb: FreestyleVm, cmd: str, timeout_s: float) -> ExecResult:
        limit_s = min(timeout_s, EXEC_CAP_S)
        body = {"command": f"sh -c {shlex.quote(cmd)}", "timeoutMs": int(limit_s * 1000)}
        result = self._json(
            ExecResponse,
            "POST",
            f"/v5/vms/{sb.id}/exec-await",
            json=body,
            timeout_s=limit_s + 30,
        )
        if result.statusCode is None:
            msg = f"command killed by the {limit_s:g}s exec timeout in {sb.slug}"
            raise TimeoutError(msg)
        return ExecResult(result.statusCode, result.stdout or "", result.stderr or "")

    def destroy(self, sb: FreestyleVm) -> None:
        self._call("DELETE", f"/v5/vms/{sb.id}", missing_ok=True)
        source = sb.fork_source
        if source is not None:
            source.copies.discard(sb.id)
            if not source.copies:
                self.delete_snapshot(source.snapshot)

    # ---- pause / resume ---------------------------------------------------------------------
    def pause(self, sb: FreestyleVm) -> None:
        data = self._json(VmData, "POST", f"/v5/vms/{sb.id}/pause")
        self._wait_state(data, "paused", TIMEOUTS["pause"])

    def resume(self, sb: FreestyleVm) -> None:
        data = self._json(VmData, "POST", f"/v5/vms/{sb.id}/start")
        self._wait_state(data, "running", TIMEOUTS["resume"])

    # ---- snapshots --------------------------------------------------------------------------
    def snapshot(self, sb: FreestyleVm, name: str) -> FreestyleSnapshot:
        # The API returns once the state is captured; VMs can boot from it immediately.
        created = self._json(
            SnapshotCreated, "POST", f"/v5/vms/{sb.id}/snapshot", json={"slug": name}
        )
        return FreestyleSnapshot(id=created.snapshotId, slug=name)

    def restore(self, snap: FreestyleSnapshot, spec: Spec) -> FreestyleVm:
        return self._boot(spec, snap.id, TIMEOUTS["restore"])

    def delete_snapshot(self, snap: FreestyleSnapshot) -> None:
        self._call("DELETE", f"/v5/snapshots/{snap.id}", missing_ok=True)

    def fork(self, sb: FreestyleVm, specs: Sequence[Spec]) -> list[FreestyleVm]:
        if not specs:
            return []
        snap = self.snapshot(sb, derived_name(specs[0].name, "fork"))
        source = _ForkSource(snap)
        copies: list[FreestyleVm] = []
        try:
            for spec in specs:
                vm = self._boot(spec, snap.id, TIMEOUTS["fork"])
                copies.append(FreestyleVm(vm.id, vm.slug, fork_source=source))
                source.copies.add(vm.id)
        except BaseException:
            for vm in copies:
                self._call("DELETE", f"/v5/vms/{vm.id}", missing_ok=True)
            self.delete_snapshot(snap)
            raise
        return copies

    # ---- network ----------------------------------------------------------------------------
    def expose_port(self, sb: FreestyleVm, port: int) -> Endpoint:
        domain = f"{derived_name(sb.slug, f'p{port}')}.style.dev"
        rule = {
            "action": "allow",
            "domain": domain,
            "protocol": "http",
            "source": {"public": True},
            "destination": {"vmId": sb.id, "port": port},
        }
        created = self._json(TlsRule, "POST", "/v5/tls", json=rule)
        return Endpoint(url=f"https://{created.domain}/")

    # ---- account ----------------------------------------------------------------------------
    def ping(self) -> None:
        self._call("GET", "/v5/vms", params={"limit": 1}, timeout_s=TIMEOUTS["ping"])

    def reap(self, prefix: str) -> int:
        if not prefix.startswith(RESOURCE_PREFIX):
            msg = f"refusing to reap {prefix!r}: the prefix must start with {RESOURCE_PREFIX!r}"
            raise ValueError(msg)
        vms = [vm for vm in self._list_vms() if (vm.slug or "").startswith(prefix)]
        snaps = [
            s for s in self._list_snapshots() if not s.public and (s.slug or "").startswith(prefix)
        ]
        for vm in vms:
            self._call("DELETE", f"/v5/vms/{vm.id}", missing_ok=True)
        for snap in snaps:
            self._call("DELETE", f"/v5/snapshots/{snap.id}", missing_ok=True)
        return len(vms) + len(snaps)

    def _list_vms(self, page: int = 100) -> list[VmData]:
        found: list[VmData] = []
        while True:
            params = {"limit": page, "offset": len(found)}
            batch = self._json(VmList, "GET", "/v5/vms", params=params).vms
            found.extend(batch)
            if len(batch) < page:
                return found

    def _list_snapshots(self, page: int = 100) -> list[SnapshotData]:
        found: list[SnapshotData] = []
        while True:
            params = {"limit": page, "offset": len(found)}
            batch = self._json(SnapshotList, "GET", "/v5/snapshots", params=params).snapshots
            found.extend(batch)
            if len(batch) < page:
                return found


# ---- errors -----------------------------------------------------------------------------------
ACCOUNT_STATUSES = frozenset({401, 402, 403})
ACCOUNT_CODE_WORDS = ("LIMIT", "QUOTA", "PLAN", "BILLING", "CREDIT", "PAYMENT")


class _ErrorBody(_Model):
    code: str = "UNKNOWN_ERROR"
    message: str = ""


def _error(response: httpx.Response, what: str) -> Exception:
    """Map a failed response to ``AccountError`` (our side) or ``FreestyleApiError``."""
    try:
        body = _ErrorBody.model_validate_json(response.content)
    except ValueError:
        body = _ErrorBody(message=response.text)
    message = " ".join(body.message.split())[:200]
    status = response.status_code
    throttled = body.code.startswith("RATE")  # RATE_LIMITED is the provider's (ADR-0009)
    if status in ACCOUNT_STATUSES or (
        not throttled and any(w in body.code for w in ACCOUNT_CODE_WORDS)
    ):
        return AccountError(f"{what}: HTTP {status} {body.code}: {message}")
    return FreestyleApiError(status, body.code, message, what)
