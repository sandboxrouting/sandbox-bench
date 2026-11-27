"""E2B adapter: offline tests against a stubbed SDK class, plus one live smoke test."""

from __future__ import annotations

import builtins
import os
import subprocess
import sys
import uuid
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, ClassVar, cast

import pytest
from e2b import (
    AuthenticationException,
    CommandExitException,
    RateLimitException,
    SandboxException,
    SnapshotInfo,
)

from sandbox_bench import providers
from sandbox_bench.adapter import AccountError, Spec
from sandbox_bench.providers.e2b import E2B, LABEL, TEMPLATE, TOKEN_HEADER, TTL_S

if TYPE_CHECKING:
    from e2b import Sandbox


# ---- stubs: only the SDK surface the adapter uses ---------------------------------------------
def throttled(message: str) -> Exception:
    return RateLimitException(message)  # type: ignore[no-untyped-call]


@dataclass
class Result:
    exit_code: int
    stdout: str
    stderr: str = ""


@dataclass
class StubCommands:
    result: Result = field(default_factory=lambda: Result(0, "ok\n"))
    error: Exception | None = None
    calls: list[tuple[str, Any, float | None]] = field(default_factory=list)

    def run(self, cmd: str, shell: Any = None, timeout: float | None = None) -> Result:
        self.calls.append((cmd, shell, timeout))
        if self.error:
            raise self.error
        return self.result


@dataclass
class Info:
    sandbox_id: str
    metadata: dict[str, str]


class Pages:
    """The SDK's paginator: ``has_next`` starts true, then follows the pages."""

    def __init__(self, pages: list[list[Any]]) -> None:
        self.pages = list(pages)

    @property
    def has_next(self) -> bool:
        return bool(self.pages)

    def next_items(self) -> list[Any]:
        return self.pages.pop(0)


class StubSandbox:
    """Stands in for ``e2b.Sandbox``: class methods act on the account, instances on one box."""

    created: ClassVar[list[dict[str, Any]]] = []
    killed: ClassVar[list[str]] = []
    deleted_snapshots: ClassVar[list[str]] = []
    listed: ClassVar[list[dict[str, Any]]] = []
    sandbox_pages: ClassVar[list[list[Info]]] = [[]]
    snapshot_pages: ClassVar[list[list[SnapshotInfo]]] = [[]]
    create_error: ClassVar[Exception | None] = None
    fork_results: ClassVar[builtins.list[Any] | None] = None

    def __init__(self, sandbox_id: str = "i1", token: str | None = "tok") -> None:  # noqa: S107
        self.sandbox_id = sandbox_id
        self.traffic_access_token = token
        self.commands = StubCommands()
        self.calls: list[tuple[str, dict[str, Any]]] = []

    @classmethod
    def reset(cls) -> None:
        cls.created, cls.killed, cls.deleted_snapshots, cls.listed = [], [], [], []
        cls.sandbox_pages, cls.snapshot_pages = [[]], [[]]
        cls.create_error, cls.fork_results = None, None

    # account-level calls
    @classmethod
    def create(cls, template: str, **kw: Any) -> StubSandbox:
        if cls.create_error:
            raise cls.create_error
        cls.created.append({"template": template, **kw})
        return cls(f"i{len(cls.created)}")

    @classmethod
    def list(cls, **kw: Any) -> Pages:
        cls.listed.append(kw)
        return Pages(cls.sandbox_pages)

    @classmethod
    def list_snapshots(cls, **kw: Any) -> Pages:
        return Pages(cls.snapshot_pages)

    @classmethod
    def delete_snapshot(cls, snapshot_id: str, **kw: Any) -> bool:
        cls.deleted_snapshots.append(snapshot_id)
        return snapshot_id != "team/gone:default"

    # per-sandbox calls (``kill`` is both, as in the SDK)
    def kill(box_or_id: StubSandbox | str, **kw: Any) -> bool:  # noqa: N805 - see above
        """``box.kill()`` or ``Sandbox.kill(sandbox_id)``."""
        StubSandbox.killed.append(box_or_id if isinstance(box_or_id, str) else box_or_id.sandbox_id)
        return True

    def pause(self, **kw: Any) -> bool:
        self.calls.append(("pause", kw))
        return True

    def connect(self, **kw: Any) -> StubSandbox:
        self.calls.append(("connect", kw))
        return self

    def create_snapshot(self, name: str, **kw: Any) -> SnapshotInfo:
        return SnapshotInfo(snapshot_id=f"team/{name}:default", names=[f"team/{name}"])

    def fork(self, count: int, **kw: Any) -> builtins.list[Any]:
        self.calls.append(("fork", {"count": count, **kw}))
        if type(self).fork_results is not None:
            return list(type(self).fork_results or [])
        return [type(self)(f"{self.sandbox_id}-f{i}") for i in range(count)]

    def get_host(self, port: int) -> str:
        return f"{port}-{self.sandbox_id}.e2b.app"


@pytest.fixture
def stub() -> type[StubSandbox]:
    StubSandbox.reset()
    return StubSandbox


def adapter(stub: type[StubSandbox]) -> E2B:
    return E2B(sdk=cast("type[Sandbox]", stub))


def sb(box: StubSandbox) -> Sandbox:
    return cast("Sandbox", box)


# ---- declarations -----------------------------------------------------------------------------
def test_declarations_are_valid() -> None:
    cls = providers.adapter_class("e2b")
    assert cls is E2B
    assert providers.validate(cls) == []
    assert (cls.size.vcpu, cls.size.memory_gib) == (2, 4)


def test_missing_key_is_an_account_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("E2B_API_KEY", raising=False)
    with pytest.raises(AccountError, match="E2B_API_KEY"):
        E2B()


def test_connection_retries_are_off_when_the_adapter_loads_the_sdk() -> None:
    # The SDK reads E2B_CONNECTION_RETRIES once, at import; in `sbx` the adapter imports it first.
    env = {k: v for k, v in os.environ.items() if k != "E2B_CONNECTION_RETRIES"}
    check = (
        "import sandbox_bench.providers.e2b, e2b.api.client_sync as c; print(c.connection_retries)"
    )
    out = subprocess.run([sys.executable, "-c", check], env=env, capture_output=True, check=True)
    assert out.stdout.strip() == b"0"


# ---- create / exec / destroy ------------------------------------------------------------------
def test_create_uses_the_standard_template_with_name_ttl_and_egress(
    stub: type[StubSandbox],
) -> None:
    a = adapter(stub)
    a.create(Spec(name="sbx-t-1"))
    a.create(Spec(name="sbx-t-2", egress=False))
    first, second = stub.created
    assert first["template"] == TEMPLATE
    assert first["metadata"] == {**LABEL, "name": "sbx-t-1"}
    assert (first["timeout"], first["retries"]) == (TTL_S, 0)
    assert (first["allow_internet_access"], second["allow_internet_access"]) == (True, False)


def test_missing_template_says_how_to_build_it(stub: type[StubSandbox]) -> None:
    stub.create_error = SandboxException(f"404: template '{TEMPLATE}' not found", status_code=404)
    with pytest.raises(AccountError, match="build-template"):
        adapter(stub).create(Spec(name="sbx-t-1"))


def test_exec_runs_under_sh_and_maps_a_failed_exit_to_a_result(stub: type[StubSandbox]) -> None:
    a, box = adapter(stub), StubSandbox()
    box.commands.result = Result(0, "hi\n", "")
    assert a.exec(sb(box), "echo hi", 5).stdout == "hi\n"
    assert box.commands.calls == [("echo hi", ("/bin/sh", "-c"), 5)]
    box.commands.error = CommandExitException(stderr="e", stdout="o", exit_code=3, error=None)
    result = a.exec(sb(box), "exit 3", 5)
    assert (result.exit_code, result.stdout, result.stderr) == (3, "o", "e")


def test_destroy_kills(stub: type[StubSandbox]) -> None:
    adapter(stub).destroy(sb(StubSandbox("i9")))
    assert stub.killed == ["i9"]


# ---- account errors ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    "error",
    [
        AuthenticationException("401: Unauthorized, please check your credentials."),
        SandboxException("403: Forbidden", status_code=403),
        throttled(
            "429: Rate limit exceeded - You have reached the maximum number of concurrent "
            "E2B sandboxes (10)."
        ),
        SandboxException("400: not enough credits", status_code=400),
    ],
)
def test_account_failures_raise_account_error(stub: type[StubSandbox], error: Exception) -> None:
    stub.create_error = error
    with pytest.raises(AccountError):
        adapter(stub).create(Spec(name="sbx-t-1"))


@pytest.mark.parametrize(
    "error",
    [
        throttled("429: Rate limit exceeded, please try again later."),
        SandboxException("500: internal error", status_code=500),
        SandboxException("404: sandbox not found", status_code=404),
    ],
)
def test_provider_failures_stay_provider_failures(
    stub: type[StubSandbox], error: Exception
) -> None:
    box = StubSandbox()
    box.commands.error = error
    with pytest.raises(type(error)):
        adapter(stub).exec(sb(box), "true", 5)


# ---- pause / snapshots / fork -----------------------------------------------------------------
def test_pause_and_resume(stub: type[StubSandbox]) -> None:
    a, box = adapter(stub), StubSandbox()
    a.pause(sb(box))
    a.resume(sb(box))
    assert box.calls == [("pause", {"retries": 0}), ("connect", {"timeout": TTL_S, "retries": 0})]


def test_snapshot_restore_and_delete(stub: type[StubSandbox]) -> None:
    a = adapter(stub)
    snap = a.snapshot(sb(StubSandbox()), "sbx-t-snap")
    assert snap == "team/sbx-t-snap:default"
    a.restore(snap, Spec(name="sbx-t-2"))
    assert stub.created[0]["template"] == snap
    a.delete_snapshot(snap)
    a.delete_snapshot("team/gone:default")  # already gone: no error
    assert stub.deleted_snapshots == [snap, "team/gone:default"]


def test_fork_returns_one_child_per_spec(stub: type[StubSandbox]) -> None:
    a, parent = adapter(stub), StubSandbox("p")
    children = a.fork(sb(parent), [Spec(name=f"sbx-t-{i}") for i in range(3)])
    assert [c.sandbox_id for c in children] == ["p-f0", "p-f1", "p-f2"]
    assert parent.calls == [("fork", {"count": 3, "timeout": TTL_S, "retries": 0})]
    assert a.fork(sb(parent), []) == []


def test_a_failed_fork_kills_the_others_and_raises(stub: type[StubSandbox]) -> None:
    ok = StubSandbox("f0")
    stub.fork_results = [ok, SandboxException("500: boom", status_code=500)]
    with pytest.raises(SandboxException, match="boom"):
        adapter(stub).fork(sb(StubSandbox("p")), [Spec(name="sbx-t-1"), Spec(name="sbx-t-2")])
    assert stub.killed == ["f0"]


# ---- ports ------------------------------------------------------------------------------------
def test_expose_port_sends_the_traffic_token_when_private(stub: type[StubSandbox]) -> None:
    a = adapter(stub)
    private = a.expose_port(sb(StubSandbox("i1", token="tok")), 8080)  # noqa: S106
    assert private.url == "https://8080-i1.e2b.app/"
    assert private.headers == {TOKEN_HEADER: "tok"}
    assert a.expose_port(sb(StubSandbox("i1", token=None)), 8080).headers == {}


# ---- reap -------------------------------------------------------------------------------------
@pytest.mark.parametrize("prefix", ["", "s", "sbx", "cc-", "sandbox-bench"])
def test_reap_refuses_foreign_prefixes(stub: type[StubSandbox], prefix: str) -> None:
    with pytest.raises(ValueError, match="refusing"):
        adapter(stub).reap(prefix)
    assert stub.killed == []


def test_reap_deletes_only_matching_resources(stub: type[StubSandbox]) -> None:
    stub.sandbox_pages = [
        [Info("a", {**LABEL, "name": "sbx-r1-1"}), Info("b", {**LABEL, "name": "sbx-r2-1"})],
        [Info("c", {**LABEL, "name": "sbx-r1-2"}), Info("d", dict(LABEL))],
    ]
    stub.snapshot_pages = [
        [SnapshotInfo("team/sbx-r1-snap:default", ["team/sbx-r1-snap"])],
        [
            SnapshotInfo("team/other:default", ["team/other"]),
            SnapshotInfo("team/sbx-r2-snap:default", ["team/sbx-r2-snap"]),
        ],
    ]
    assert adapter(stub).reap("sbx-r1-") == 3
    assert stub.killed == ["a", "c"]
    assert stub.deleted_snapshots == ["team/sbx-r1-snap:default"]
    query = stub.listed[0]["query"]
    assert query.metadata == LABEL  # only this harness's sandboxes are listed


def test_ping_lists_one_sandbox(stub: type[StubSandbox]) -> None:
    adapter(stub).ping()
    assert stub.listed == [{"limit": 1, "retries": 0}]


# ---- live -------------------------------------------------------------------------------------
@pytest.mark.live
@pytest.mark.skipif(not os.environ.get("E2B_API_KEY"), reason="needs E2B_API_KEY")
def test_live_create_exec_destroy() -> None:
    a = E2B()
    a.ping()
    box = a.create(Spec(name=f"sbx-test-{uuid.uuid4().hex[:8]}"))
    try:
        assert a.exec(box, "echo hi", 60).stdout == "hi\n"
        assert a.exec(box, "echo err >&2; exit 3", 60).exit_code == 3
        assert a.exec(box, "nproc; free -g | awk '/Mem/{print $2}'", 60).stdout.split()[0] == "2"
    finally:
        a.destroy(box)
