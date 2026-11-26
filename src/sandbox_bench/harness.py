"""The harness context ``h`` that a probe action runs against.

``h`` owns every clock boundary (METHODOLOGY §4), every timeout and all cleanup, so probe code
only says *what* to do. Every adapter call goes through ``h.call``, which runs it in a worker
thread with a deadline and wraps whatever it raises in ``ProviderError``. That wrapping is how
a provider fault (a failure) is kept apart from a harness bug, which is never wrapped and so
crashes, or is excluded in a non-strict run.
"""

from __future__ import annotations

import secrets
import statistics
import threading
import time
from collections.abc import Callable, Iterable, Mapping
from concurrent.futures import Future, wait
from dataclasses import dataclass, field
from itertools import count
from typing import Any

import httpx

from sandbox_bench.adapter import AccountError, Endpoint, ExecResult, Spec
from sandbox_bench.benchmark import TIMEOUTS
from sandbox_bench.providers import AnyAdapter
from sandbox_bench.schema import Evidence


class OperationTimeoutError(TimeoutError):
    """An operation ran past its timeout. A failure, never a capped sample."""


class ProviderError(Exception):
    """An adapter call failed, or the sandbox never became ready."""

    def __init__(self, op: str, cause: BaseException) -> None:
        super().__init__(f"{type(cause).__name__}: {cause}")
        self.op = op


@dataclass(frozen=True, slots=True)
class Check:
    """One verifier's verdict, before it becomes a ``schema.Verdict``."""

    ok: bool
    evidence: Evidence = field(default_factory=dict)
    error: str | None = None


def http_get(endpoint: Endpoint) -> str:
    response = httpx.get(endpoint.url, headers=dict(endpoint.headers), timeout=10)
    response.raise_for_status()
    return response.text


@dataclass(frozen=True, slots=True)
class Env:
    """What the offline tests replace: time, the runner's HTTP client and the timeouts."""

    now: Callable[[], float] = time.perf_counter
    sleep: Callable[[float], None] = time.sleep
    http_get: Callable[[Endpoint], str] = http_get
    timeouts: Mapping[str, float] = TIMEOUTS


class Pacer:
    """Keeps ``pacing_s`` between one provider's calls, and counts the time spent waiting so
    timers can take it back out: pacing happens outside the clock."""

    def __init__(self, gap_s: float, env: Env) -> None:
        self.gap_s, self.env = gap_s, env
        self.last, self.waited = -float("inf"), 0.0

    def wait(self) -> None:
        delay = self.last + self.gap_s - self.env.now()
        if delay > 0:
            self.env.sleep(delay)
            self.waited += delay
        self.last = self.env.now()


def with_deadline[T](fn: Callable[..., T], args: Iterable[Any], timeout_s: float, op: str) -> T:
    """Run a blocking call in a daemon thread. On timeout the thread is abandoned; anything it
    creates late carries the run's name prefix, so the reaper removes it."""
    future: Future[T] = Future()

    def target() -> None:
        try:
            future.set_result(fn(*args))
        except BaseException as exc:  # noqa: BLE001 - handed to the caller through the future
            future.set_exception(exc)

    threading.Thread(target=target, daemon=True, name=f"sbx-{op}").start()
    if not wait([future], timeout=timeout_s).done:
        msg = f"{op} did not finish within {timeout_s:g} s"
        raise OperationTimeoutError(msg)
    return future.result()


class Harness:
    """One attempt of one action against one provider."""

    def __init__(
        self,
        adapter: AnyAdapter,
        *,
        prefix: str,
        wanted: Iterable[str],
        timings: Iterable[str],
        env: Env,
        pacer: Pacer,
    ) -> None:
        self.adapter, self.prefix, self.env, self.pacer = adapter, prefix, env, pacer
        self.wanted, self.declared = frozenset(wanted), frozenset(timings)
        self.timings: dict[str, float] = {}
        self.start_evidence: Evidence = {}
        self.default_create = True
        self.log: list[str] = []
        self._sandboxes: list[Any] = []
        self._snapshots: list[Any] = []
        self._serial = count(1)
        self._started = False

    def wants(self, probe: str) -> bool:
        return probe in self.wanted

    # ---- adapter calls -----------------------------------------------------------------------
    def call[T](self, op: str, fn: Callable[..., T], *args: Any) -> T:
        self.pacer.wait()
        try:
            return with_deadline(fn, args, self.env.timeouts[op], op)
        except AccountError:
            raise
        except Exception as exc:
            raise ProviderError(op, exc) from exc

    def timed[T](self, metric: str, fn: Callable[[], T]) -> T:
        """Record how long ``fn`` takes as ``metric``, minus any pacing, if it succeeds."""
        if metric not in self.declared:
            msg = f"timing {metric!r} isn't declared by the action"
            raise ValueError(msg)
        waited, t0 = self.pacer.waited, self.env.now()
        result = fn()
        self.timings[metric] = round(self.env.now() - t0 - (self.pacer.waited - waited), 6)
        return result

    def median_of[T](self, metric: str, fn: Callable[[], T], n: int) -> list[T]:
        """Run ``fn`` ``n`` times and record the median duration as ``metric``."""
        results, durations = [], []
        for _ in range(n):
            results.append(self.timed(metric, fn))
            durations.append(self.timings[metric])
        self.timings[metric] = statistics.median(durations)
        return results

    def sh(self, sb: Any, script: str) -> ExecResult:
        return self.call("exec", self.adapter.exec, sb, script, self.env.timeouts["exec"])

    def _spec(self, egress: bool = True) -> Spec:
        return Spec(name=f"{self.prefix}-{next(self._serial)}", egress=egress)

    def _ready(self, sb: Any, op: str, started: float) -> None:
        """Echo until it succeeds: "ready" always means a command succeeded (METHODOLOGY §4)."""
        token = f"sbx-ready-{secrets.token_hex(4)}"
        deadline = started + self.env.timeouts[op]
        while True:
            try:
                out = self.sh(sb, f"echo {token}")
                if out.ok and out.stdout.strip() == token:
                    return
                last = f"exit {out.exit_code}, stdout {out.stdout.strip()[:80]!r}"
            except ProviderError as exc:
                last = str(exc)
            if self.env.now() >= deadline:
                msg = f"no command succeeded within {self.env.timeouts[op]:g} s; last: {last}"
                raise ProviderError(op, OperationTimeoutError(msg))
            self.env.sleep(0.1)

    def _new(self, op: str, fn: Callable[..., Any], *args: Any) -> Any:
        """Call ``fn`` to make one sandbox, track it for cleanup, and wait until it's ready."""
        started = self.env.now()
        sb = self.call(op, fn, *args)
        self._sandboxes.append(sb)
        self._ready(sb, op, started)
        return sb

    # ---- operations, each with its clock boundary (METHODOLOGY §4) ---------------------------
    def create(self, *, egress: bool = True) -> Any:
        """Create a sandbox. The attempt's first create is timed as Start, and only it says
        whether the attempt used a default create."""
        spec = self._spec(egress)
        if self._started:
            return self._new("create", self.adapter.create, spec)
        self._started, self.default_create = True, egress
        return self.timed("start", lambda: self._new("create", self.adapter.create, spec))

    def pause(self, sb: Any) -> None:
        self.timed("pause", lambda: self.call("pause", self.adapter.pause, sb))

    def resume(self, sb: Any) -> None:
        def go() -> None:
            started = self.env.now()
            self.call("resume", self.adapter.resume, sb)
            self._ready(sb, "resume", started)

        self.timed("resume", go)

    def snapshot(self, sb: Any) -> Any:
        name = f"{self.prefix}-snap-{next(self._serial)}"
        snap = self.timed(
            "snapshot", lambda: self.call("snapshot", self.adapter.snapshot, sb, name)
        )
        self._snapshots.append(snap)
        return snap

    def restore(self, snap: Any) -> Any:
        spec = self._spec()
        return self.timed("restore", lambda: self._new("restore", self.adapter.restore, snap, spec))

    def fork(self, sb: Any, n: int, *, timed: bool = True) -> list[Any]:
        """Fork ``n`` children. Timed until the first command succeeds in the first child."""
        specs = [self._spec() for _ in range(n)]

        def go() -> list[Any]:
            started = self.env.now()
            children: list[Any] = self.call("fork", self.adapter.fork, sb, specs)
            self._sandboxes.extend(children)
            if len(children) != n:
                msg = f"asked for {n} children, got {len(children)}"
                raise ProviderError("fork", ValueError(msg))
            self._ready(children[0], "fork", started)
            return children

        children = self.timed("fork", go) if timed else go()
        started = self.env.now()
        for child in children[1:]:
            self._ready(child, "fork", started)
        return children

    def expose_port(self, sb: Any, port: int) -> Endpoint:
        endpoint: Endpoint = self.call("expose_port", self.adapter.expose_port, sb, port)
        return endpoint

    def destroy(self, sb: Any) -> None:
        """Destroy early, outside any clock, to stay under concurrent-sandbox limits."""
        self._sandboxes.remove(sb)
        self._quietly("destroy", self.adapter.destroy, sb)

    def cleanup(self) -> None:
        """Destroy everything this attempt created: sandboxes first, then snapshots."""
        for sb in reversed(self._sandboxes):
            self._quietly("destroy", self.adapter.destroy, sb)
        for snap in reversed(self._snapshots):
            self._quietly("delete_snapshot", self.adapter.delete_snapshot, snap)
        self._sandboxes.clear()
        self._snapshots.clear()

    def _quietly(self, op: str, fn: Callable[..., Any], arg: Any) -> None:
        try:
            self.call(op, fn, arg)
        except (ProviderError, AccountError) as exc:
            self.log.append(f"{self.prefix}: cleanup {op} failed: {exc}")
