"""Offline tests of the Freestyle adapter against a fake REST API (``httpx.MockTransport``)."""

from __future__ import annotations

import json
from typing import Any

import httpx
import pytest

from sandbox_bench import providers
from sandbox_bench.adapter import AccountError, Spec
from sandbox_bench.providers.freestyle import (
    ALLOW_INTERNET,
    BASE_SNAPSHOT,
    Freestyle,
    FreestyleApiError,
    FreestyleSnapshot,
    FreestyleVm,
    derived_name,
)

KEY = "test-key-not-real"


class FakeApi:
    """Just enough of ``api.freestyle.sh/v5`` to drive the adapter."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, str, Any]] = []
        self.vms: dict[str, dict[str, Any]] = {}
        self.snapshots: dict[str, dict[str, Any]] = {
            "sh-base": {"id": "sh-base", "slug": "ubuntu-sm", "public": True},
        }
        self.create_state = "running"
        self.fail: dict[tuple[str, str], tuple[int, dict[str, str]]] = {}
        self.exec_result: dict[str, Any] = {"statusCode": 0, "stdout": "hi\n", "stderr": ""}
        self.next_id = 0

    def _id(self, prefix: str) -> str:
        self.next_id += 1
        return f"{prefix}-{self.next_id}"

    def __call__(self, request: httpx.Request) -> httpx.Response:
        assert request.headers["authorization"] == f"Bearer {KEY}"
        body = json.loads(request.content) if request.content else None
        method, path = request.method, request.url.path
        self.calls.append((method, path, body))
        for (m, prefix), (status, err) in self.fail.items():
            if m == method and path.startswith(prefix):
                return httpx.Response(status, json=err)
        parts = path.removeprefix("/v5/").split("/")
        return self._route(method, parts, body, request)

    def _route(  # noqa: PLR0911 - one return per fake route
        self, method: str, parts: list[str], body: Any, request: httpx.Request
    ) -> httpx.Response:
        match method, parts:
            case "POST", ["vms"]:
                vm = {"id": self._id("vm"), "slug": body["slug"], "state": self.create_state}
                self.vms[vm["id"]] = dict(vm, state="running")
                return httpx.Response(201, json=vm | {"resources": {"cpu": 2}})
            case "GET", ["vms"]:
                return self._page(request, "vms", list(self.vms.values()))
            case "GET", ["vms", vm_id] if vm_id in self.vms:
                return httpx.Response(200, json=self.vms[vm_id])
            case "DELETE", ["vms", vm_id] if vm_id in self.vms:
                del self.vms[vm_id]
                return httpx.Response(204)
            case "POST", ["vms", vm_id, "exec-await"] if vm_id in self.vms:
                return httpx.Response(200, json=self.exec_result)
            case "POST", ["vms", vm_id, "pause"] if vm_id in self.vms:
                return httpx.Response(200, json=self.vms[vm_id] | {"state": "paused"})
            case "POST", ["vms", vm_id, "start"] if vm_id in self.vms:
                return httpx.Response(200, json=self.vms[vm_id] | {"state": "starting"})
            case "POST", ["vms", vm_id, "snapshot"] if vm_id in self.vms:
                snap = {"id": self._id("sh"), "slug": body["slug"], "public": False}
                self.snapshots[snap["id"]] = snap
                return httpx.Response(200, json={"snapshotId": snap["id"], "snapshot": snap})
            case "GET", ["snapshots"]:
                return self._page(request, "snapshots", list(self.snapshots.values()))
            case "DELETE", ["snapshots", snap_id] if snap_id in self.snapshots:
                del self.snapshots[snap_id]
                return httpx.Response(204)
            case "POST", ["tls"]:
                return httpx.Response(200, json={"id": "tls-1", "domain": body["domain"]})
        return httpx.Response(404, json={"code": "NOT_FOUND", "message": "not found"})

    @staticmethod
    def _page(request: httpx.Request, key: str, items: list[Any]) -> httpx.Response:
        offset = int(request.url.params.get("offset", 0))
        limit = int(request.url.params.get("limit", 100))
        return httpx.Response(200, json={key: items[offset : offset + limit]})

    def paths(self, method: str) -> list[str]:
        return [p for m, p, _ in self.calls if m == method]


@pytest.fixture
def api() -> FakeApi:
    return FakeApi()


@pytest.fixture
def fs(api: FakeApi) -> Freestyle:
    return Freestyle(KEY, transport=httpx.MockTransport(api))


def test_declarations_are_valid() -> None:
    cls = providers.adapter_class("freestyle")
    assert cls is Freestyle
    assert providers.validate(cls) == []


def test_missing_key_is_an_account_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("FREESTYLE_API_KEY", raising=False)
    with pytest.raises(AccountError, match="FREESTYLE_API_KEY"):
        Freestyle()


@pytest.mark.parametrize(("egress", "rules"), [(True, [ALLOW_INTERNET]), (False, [])])
def test_create_maps_spec(api: FakeApi, fs: Freestyle, egress: bool, rules: list[Any]) -> None:
    vm = fs.create(Spec(name="sbx-t-a", egress=egress))
    assert vm == FreestyleVm(id="vm-1", slug="sbx-t-a")
    _, _, body = api.calls[0]
    assert body == {"snapshotId": BASE_SNAPSHOT, "slug": "sbx-t-a", "firewall": {"rules": rules}}


def test_create_waits_until_running(api: FakeApi, fs: Freestyle) -> None:
    api.create_state = "starting"
    fs.create(Spec(name="sbx-t-a"))
    assert api.paths("GET") == ["/v5/vms/vm-1"]


def test_exec(api: FakeApi, fs: Freestyle) -> None:
    vm = fs.create(Spec(name="sbx-t-a"))
    api.exec_result = {"statusCode": 3, "stdout": "o", "stderr": "e"}
    result = fs.exec(vm, "echo 'x' && exit 3", timeout_s=900)
    assert (result.exit_code, result.stdout, result.stderr) == (3, "o", "e")
    _, path, body = api.calls[-1]
    assert path == "/v5/vms/vm-1/exec-await"
    assert body == {"command": "sh -c 'echo '\"'\"'x'\"'\"' && exit 3'", "timeoutMs": 300_000}


def test_exec_killed_by_timeout_raises(api: FakeApi, fs: Freestyle) -> None:
    vm = fs.create(Spec(name="sbx-t-a"))
    api.exec_result = {"statusCode": None, "stdout": "", "stderr": ""}
    with pytest.raises(TimeoutError, match="1s exec timeout"):
        fs.exec(vm, "sleep 5", timeout_s=1)


def test_destroy_is_idempotent(api: FakeApi, fs: Freestyle) -> None:
    vm = fs.create(Spec(name="sbx-t-a"))
    fs.destroy(vm)
    fs.destroy(vm)
    assert api.vms == {}


def test_pause_and_resume(api: FakeApi, fs: Freestyle) -> None:
    vm = fs.create(Spec(name="sbx-t-a"))
    fs.pause(vm)
    fs.resume(vm)  # the start answer says "starting", so it polls until running
    assert api.paths("POST")[1:] == ["/v5/vms/vm-1/pause", "/v5/vms/vm-1/start"]
    assert api.paths("GET") == ["/v5/vms/vm-1"]


def test_snapshot_restore_delete(api: FakeApi, fs: Freestyle) -> None:
    vm = fs.create(Spec(name="sbx-t-a"))
    snap = fs.snapshot(vm, "sbx-t-snap")
    assert snap == FreestyleSnapshot(id="sh-2", slug="sbx-t-snap")
    copy = fs.restore(snap, Spec(name="sbx-t-b"))
    assert api.calls[-1][2]["snapshotId"] == "sh-2"
    assert copy.slug == "sbx-t-b"
    fs.delete_snapshot(snap)
    fs.delete_snapshot(snap)
    assert "sh-2" not in api.snapshots


def test_fork_deletes_its_snapshot_with_the_last_copy(api: FakeApi, fs: Freestyle) -> None:
    parent = fs.create(Spec(name="sbx-t-p"))
    copies = fs.fork(parent, [Spec(name=f"sbx-t-k{i}") for i in range(3)])
    assert [c.slug for c in copies] == ["sbx-t-k0", "sbx-t-k1", "sbx-t-k2"]
    fork_snaps = [s for s in api.snapshots.values() if s["slug"] == "sbx-t-k0-fork"]
    assert len(fork_snaps) == 1
    fs.destroy(copies[0])
    fs.destroy(copies[1])
    assert fork_snaps[0]["id"] in api.snapshots
    fs.destroy(copies[2])
    assert fork_snaps[0]["id"] not in api.snapshots
    assert list(api.vms) == [parent.id]


def test_failed_fork_cleans_up(api: FakeApi, fs: Freestyle) -> None:
    parent = fs.create(Spec(name="sbx-t-p"))
    calls = 0

    real = api._route

    def flaky(method: str, parts: list[str], body: Any, request: httpx.Request) -> httpx.Response:
        nonlocal calls
        if (method, parts) == ("POST", ["vms"]):
            calls += 1
            if calls == 3:
                return httpx.Response(500, json={"code": "INTERNAL_ERROR", "message": "boom"})
        return real(method, parts, body, request)

    api._route = flaky  # type: ignore[method-assign]
    with pytest.raises(FreestyleApiError, match="HTTP 500"):
        fs.fork(parent, [Spec(name=f"sbx-t-k{i}") for i in range(3)])
    assert list(api.vms) == [parent.id]
    assert list(api.snapshots) == ["sh-base"]


def test_expose_port(api: FakeApi, fs: Freestyle) -> None:
    vm = fs.create(Spec(name="sbx-t-a"))
    endpoint = fs.expose_port(vm, 8080)
    assert endpoint.url == "https://sbx-t-a-p8080.style.dev/"
    assert endpoint.headers == {}
    assert api.calls[-1][2] == {
        "action": "allow",
        "domain": "sbx-t-a-p8080.style.dev",
        "protocol": "http",
        "source": {"public": True},
        "destination": {"vmId": "vm-1", "port": 8080},
    }


def test_derived_name_fits_a_slug() -> None:
    assert derived_name("sbx-short", "fork") == "sbx-short-fork"
    long = derived_name("sbx-" + "x" * 80, "p8080")
    assert len(long) == 63
    assert long.startswith("sbx-x")
    assert long.endswith("-p8080")
    assert long == derived_name("sbx-" + "x" * 80, "p8080")


@pytest.mark.parametrize(
    ("status", "code", "account"),
    [
        (401, "UNAUTHORIZED", True),
        (402, "PAYMENT_REQUIRED", True),
        (403, "FORBIDDEN", True),
        (429, "LIMIT_EXCEEDED", True),  # a plan limit
        (429, "RATE_LIMITED", False),  # throttling
        (409, "TLS_RULE_LIMIT", True),
        (409, "CONFLICT", False),
        (500, "INTERNAL_ERROR", False),
    ],
)
def test_error_mapping(api: FakeApi, fs: Freestyle, status: int, code: str, account: bool) -> None:
    api.fail[("POST", "/v5/vms")] = (status, {"code": code, "message": "x " * 300})
    expected = AccountError if account else FreestyleApiError
    with pytest.raises(expected, match=f"HTTP {status} {code}") as info:
        fs.create(Spec(name="sbx-t-a"))
    assert KEY not in str(info.value)
    assert len(str(info.value)) < 300


def test_non_json_error_body(api: FakeApi, fs: Freestyle) -> None:
    def gateway(request: httpx.Request) -> httpx.Response:
        return httpx.Response(502, text="<html>bad gateway</html>")

    broken = Freestyle(KEY, transport=httpx.MockTransport(gateway))
    with pytest.raises(FreestyleApiError, match="HTTP 502 UNKNOWN_ERROR: <html>bad gateway"):
        broken.ping()


@pytest.mark.parametrize("prefix", ["", "sb", "cc-", "other-", "SBX-"])
def test_reap_refuses_foreign_prefixes(api: FakeApi, fs: Freestyle, prefix: str) -> None:
    with pytest.raises(ValueError, match="refusing to reap"):
        fs.reap(prefix)
    assert api.calls == []


def test_reap_deletes_only_matching_private_resources(api: FakeApi, fs: Freestyle) -> None:
    for i in range(150):  # more than one page
        api.vms[f"vm-x{i}"] = {"id": f"vm-x{i}", "slug": f"sbx-r1-{i}", "state": "running"}
    api.vms["vm-other"] = {"id": "vm-other", "slug": "cc-mine", "state": "running"}
    api.vms["vm-noslug"] = {"id": "vm-noslug", "slug": None, "state": "paused"}
    api.snapshots["sh-a"] = {"id": "sh-a", "slug": "sbx-r1-snap", "public": False}
    api.snapshots["sh-b"] = {"id": "sh-b", "slug": "other-keep", "public": False}
    api.snapshots["sh-c"] = {"id": "sh-c", "slug": "sbx-r1-public", "public": True}
    assert fs.reap("sbx-r1-") == 151
    assert set(api.vms) == {"vm-other", "vm-noslug"}
    assert set(api.snapshots) == {"sh-base", "sh-b", "sh-c"}
