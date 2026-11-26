"""Daytona adapter: offline tests against a stubbed SDK client, plus one live smoke test."""

from __future__ import annotations

import os
import uuid
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, cast

import pytest
from daytona.v0 import (
    DaytonaAuthenticationError,
    DaytonaBadRequestError,
    DaytonaFileAccessDeniedError,
    DaytonaForbiddenError,
    DaytonaInternalServerError,
    DaytonaNotFoundError,
    DaytonaRateLimitError,
)
from daytona_api_client import SandboxState, SnapshotState

from sandbox_bench import providers
from sandbox_bench.adapter import AccountError, Spec
from sandbox_bench.providers.daytona import (
    PREVIEW_TOKEN_HEADER,
    SNAPSHOT,
    STALE_AFTER_S,
    TARGET,
    DaytonaContainer,
)

if TYPE_CHECKING:
    from daytona import DaytonaV0Client
    from daytona.v0 import Sandbox


# ---- stubs: only the SDK surface the adapter uses ---------------------------------------------
@dataclass
class Response:
    exit_code: int
    result: str


@dataclass
class Link:
    url: str
    token: str | None


@dataclass
class StubProcess:
    response: Response = field(default_factory=lambda: Response(0, "ok\n"))
    calls: list[tuple[str, int | None]] = field(default_factory=list)
    error: Exception | None = None

    def exec(self, command: str, timeout: int | None = None) -> Response:
        self.calls.append((command, timeout))
        if self.error:
            raise self.error
        return self.response


@dataclass
class StubSandbox:
    name: str
    state: SandboxState = SandboxState.STARTED
    public: bool = False
    process: StubProcess = field(default_factory=StubProcess)
    deleted: int = 0
    delete_error: Exception | None = None
    snapshots_made: list[str] = field(default_factory=list)

    def delete(self, timeout: float | None = 60, wait: bool = False) -> None:
        if self.delete_error:
            raise self.delete_error
        self.deleted += 1

    def create_snapshot(self, name: str, timeout: float | None = 60) -> None:
        self.snapshots_made.append(name)

    def get_preview_link(self, port: int, request_timeout: float | None = None) -> Link:
        return Link(f"https://{port}-abc.proxy.daytona.works", "tok")


@dataclass
class StubSnapshot:
    name: str
    state: SnapshotState = SnapshotState.ACTIVE
    general: bool = False
    error_reason: str | None = None


@dataclass
class Page:
    items: list[StubSnapshot]
    total_pages: int


@dataclass
class StubSnapshots:
    pages: list[list[StubSnapshot]] = field(default_factory=lambda: [[]])
    states: list[SnapshotState] = field(default_factory=list)
    deleted: list[str] = field(default_factory=list)

    def list(self, page: int | None = None, limit: int | None = None) -> Page:
        return Page(self.pages[(page or 1) - 1], len(self.pages))

    def get(self, name: str) -> StubSnapshot:
        return StubSnapshot(name, self.states.pop(0) if self.states else SnapshotState.ACTIVE)

    def delete(self, snapshot: str) -> None:
        if snapshot == "sbx-gone":
            raise DaytonaNotFoundError("gone", status_code=404)
        self.deleted.append(snapshot)


@dataclass
class StubClient:
    sandboxes: list[StubSandbox] = field(default_factory=list)
    snapshot: StubSnapshots = field(default_factory=StubSnapshots)
    created: list[Any] = field(default_factory=list)
    create_error: Exception | None = None

    def create(self, params: Any, timeout: float = 60) -> StubSandbox:
        if self.create_error:
            raise self.create_error
        self.created.append(params)
        return StubSandbox(params.name)

    def list(self) -> list[StubSandbox]:
        return self.sandboxes


def adapter(client: StubClient) -> DaytonaContainer:
    return DaytonaContainer(client=cast("DaytonaV0Client", client))


def sb(stub: StubSandbox) -> Sandbox:
    return cast("Sandbox", stub)


# ---- declarations -----------------------------------------------------------------------------
def test_declarations_are_valid() -> None:
    cls = providers.adapter_class("daytona")
    assert cls is DaytonaContainer
    assert providers.validate(cls) == []
    assert not {"pause-keeps-memory", "snapshot-keeps-memory", "fork-keeps-memory"} & set(
        cls.offers
    )


# ---- create / exec / destroy ------------------------------------------------------------------
def test_create_uses_medium_snapshot_in_us() -> None:
    client = StubClient()
    adapter(client).create(Spec(name="sbx-t-1"))
    (params,) = client.created
    assert (params.snapshot, params.name, params.target) == (SNAPSHOT, "sbx-t-1", TARGET)
    assert params.network_block_all is None
    assert params.ttl_minutes > 0
    assert params.auto_stop_interval > 0


def test_create_without_egress_blocks_network() -> None:
    client = StubClient()
    adapter(client).create(Spec(name="sbx-t-1", egress=False))
    assert client.created[0].network_block_all is True


def test_exec_wraps_in_sh_and_maps_result() -> None:
    box = StubSandbox("sbx-t-1")
    box.process.response = Response(7, "out\nerr\n")
    result = adapter(StubClient()).exec(sb(box), "echo 'a b' && exit 7", 2.5)
    assert box.process.calls == [("sh -c 'echo '\"'\"'a b'\"'\"' && exit 7'", 3)]
    assert (result.exit_code, result.stdout, result.stderr) == (7, "out\nerr\n", "")


def test_destroy_is_idempotent() -> None:
    box = StubSandbox("sbx-t-1")
    a = adapter(StubClient())
    a.destroy(sb(box))
    box.delete_error = DaytonaNotFoundError("not found", status_code=404)
    a.destroy(sb(box))
    assert box.deleted == 1


def test_create_after_idle_starts_a_new_client(monkeypatch: pytest.MonkeyPatch) -> None:
    clients: list[StubClient] = []

    class FakeDaytona:
        def __init__(self) -> None:
            self.v0 = StubClient()
            clients.append(self.v0)

    now = [1000.0]
    monkeypatch.setattr("sandbox_bench.providers.daytona.Daytona", FakeDaytona)
    monkeypatch.setattr("sandbox_bench.providers.daytona.time.monotonic", lambda: now[0])
    a = DaytonaContainer()
    box = a.create(Spec(name="sbx-t-1"))
    a.exec(box, "true", 5)
    now[0] += STALE_AFTER_S - 1
    a.create(Spec(name="sbx-t-2"))
    assert len(clients) == 1  # still fresh: reused
    now[0] += STALE_AFTER_S + 1
    a.create(Spec(name="sbx-t-3"))
    assert len(clients) == 2
    assert [p.name for p in clients[1].created] == ["sbx-t-3"]


# ---- account errors ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    "error",
    [
        DaytonaAuthenticationError("Invalid credentials", status_code=401),
        DaytonaForbiddenError("Organization is suspended", status_code=403),
        DaytonaBadRequestError("Total CPU quota exceeded (10)", status_code=400),
    ],
)
def test_account_failures_raise_account_error(error: Exception) -> None:
    with pytest.raises(AccountError):
        adapter(StubClient(create_error=error)).create(Spec(name="sbx-t-1"))


def test_throttling_is_a_provider_failure_but_a_plan_quota_is_ours() -> None:
    throttled = DaytonaRateLimitError("Rate limit exceeded", status_code=429)
    with pytest.raises(DaytonaRateLimitError):
        adapter(StubClient(create_error=throttled)).create(Spec(name="sbx-t-1"))
    quota = DaytonaRateLimitError("Sandbox quota exceeded", status_code=429)
    with pytest.raises(AccountError):
        adapter(StubClient(create_error=quota)).create(Spec(name="sbx-t-1"))


@pytest.mark.parametrize(
    "error",
    [
        DaytonaInternalServerError("boom", status_code=500),
        DaytonaFileAccessDeniedError("denied", status_code=403, source="daemon"),
    ],
)
def test_provider_failures_stay_provider_failures(error: Exception) -> None:
    box = StubSandbox("sbx-t-1")
    box.process.error = error
    with pytest.raises(type(error)):
        adapter(StubClient()).exec(sb(box), "true", 5)


# ---- snapshots --------------------------------------------------------------------------------
def test_snapshot_waits_until_active(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("time.sleep", lambda _s: None)
    client = StubClient()
    client.snapshot.states = [SnapshotState.PENDING, SnapshotState.BUILDING, SnapshotState.ACTIVE]
    box = StubSandbox("sbx-t-1")
    assert adapter(client).snapshot(sb(box), "sbx-t-snap") == "sbx-t-snap"
    assert box.snapshots_made == ["sbx-t-snap"]
    assert client.snapshot.states == []


def test_snapshot_error_state_raises() -> None:
    client = StubClient()
    client.snapshot.states = [SnapshotState.ERROR]
    with pytest.raises(RuntimeError, match="failed"):
        adapter(client).snapshot(sb(StubSandbox("sbx-t-1")), "sbx-t-snap")


def test_restore_creates_from_snapshot_and_delete_is_idempotent() -> None:
    client = StubClient()
    a = adapter(client)
    a.restore("sbx-t-snap", Spec(name="sbx-t-2"))
    assert client.created[0].snapshot == "sbx-t-snap"
    a.delete_snapshot("sbx-t-snap")
    a.delete_snapshot("sbx-gone")
    assert client.snapshot.deleted == ["sbx-t-snap"]


# ---- ports ------------------------------------------------------------------------------------
def test_expose_port_sends_token_for_private_sandbox() -> None:
    a = adapter(StubClient())
    private = a.expose_port(sb(StubSandbox("sbx-t-1")), 8080)
    assert private.url.startswith("https://8080-")
    assert private.headers == {PREVIEW_TOKEN_HEADER: "tok"}
    assert a.expose_port(sb(StubSandbox("sbx-t-1", public=True)), 8080).headers == {}


# ---- reap -------------------------------------------------------------------------------------
@pytest.mark.parametrize("prefix", ["", "s", "sbx", "cc-", "other-"])
def test_reap_refuses_foreign_prefixes(prefix: str) -> None:
    client = StubClient(sandboxes=[StubSandbox("cc-x")])
    with pytest.raises(ValueError, match="refusing"):
        adapter(client).reap(prefix)
    assert client.sandboxes[0].deleted == 0


def test_reap_deletes_only_matching_resources() -> None:
    mine, other_run = StubSandbox("sbx-r1-a"), StubSandbox("sbx-r2-a")
    foreign, dying = StubSandbox("1f2e3d4c"), StubSandbox("sbx-r1-b", SandboxState.DESTROYING)
    client = StubClient(sandboxes=[mine, other_run, foreign, dying])
    client.snapshot.pages = [
        [StubSnapshot("other-x"), StubSnapshot("sbx-r1-snap"), StubSnapshot("daytona-medium")],
        [
            StubSnapshot("sbx-r1-old", SnapshotState.REMOVING),
            StubSnapshot("sbx-r1-snap2"),
            StubSnapshot("sbx-r1-general", general=True),
        ],
    ]
    assert adapter(client).reap("sbx-r1-") == 3
    assert [s.deleted for s in (mine, other_run, foreign, dying)] == [1, 0, 0, 0]
    assert client.snapshot.deleted == ["sbx-r1-snap", "sbx-r1-snap2"]


# ---- live -------------------------------------------------------------------------------------
@pytest.mark.live
@pytest.mark.skipif(not os.environ.get("DAYTONA_API_KEY"), reason="needs DAYTONA_API_KEY")
def test_live_create_exec_destroy() -> None:
    a = DaytonaContainer()
    a.ping()
    box = a.create(Spec(name=f"sbx-test-{uuid.uuid4().hex[:8]}"))
    try:
        assert a.exec(box, "echo hi", 60).stdout == "hi\n"
        assert a.exec(box, "exit 3", 60).exit_code == 3
    finally:
        a.destroy(box)
