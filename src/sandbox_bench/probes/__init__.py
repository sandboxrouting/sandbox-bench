"""Probe actions: one module per action, each yielding one or more probe verdicts.

An action is a function ``fn(h) -> {probe: Check}`` registered with ``@action``. It creates its
sandboxes through ``h`` and uses only adapter operations (via ``h``) and ``sh`` inside the
sandbox. It returns a verdict for every probe in ``h.wanted``; the harness drops the rest.

``Context`` is the ``h`` actions get: the harness's operations and clocks, plus the verifiers
probes share. Verifiers and guest scripts live here because they grow with the probes.
"""

from __future__ import annotations

import importlib
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Final

from sandbox_bench.benchmark import COUNTER_GAP_S, FILE_BYTES, PROBES
from sandbox_bench.harness import Check, Harness, ProviderError
from sandbox_bench.probes import guest
from sandbox_bench.schema import Evidence

TIMINGS: Final = frozenset({"start", "exec", "pause", "resume", "snapshot", "restore", "fork"})
MODULES: Final = ("basics", "network", "pause", "snapshot", "fork")
COUNTER_TAG: Final = "sbx-counter"


@dataclass(frozen=True, slots=True)
class Written:
    name: str
    sha256: str | None


class Context(Harness):
    def create(self, *, egress: bool = True) -> Any:
        """Create a sandbox; the first one is timed as Start and gets boot evidence."""
        first = not self._started
        sb = super().create(egress=egress)
        if first:  # outside the clock: Start has already stopped
            boot = guest.parse(self.sh(sb, guest.BOOT).stdout)
            self.start_evidence = {k: v for k, v in boot.items() if k in {"uptime", "boot_id"}}
        return sb

    @staticmethod
    def isolated(fn: Callable[[], Check]) -> Check:
        """Run one probe's steps so that a provider fault fails only that probe."""
        try:
            return fn()
        except ProviderError as exc:
            return Check(False, {"op": exc.op}, str(exc))

    def start_counter(self, sb: Any) -> guest.CounterRead:
        """Start the memory-check counter and its RAM buffer (METHODOLOGY §3); first read."""
        return guest.CounterRead.parse(self.sh(sb, guest.counter_start(COUNTER_TAG)).stdout)

    def read_counter(self, sb: Any) -> guest.CounterRead:
        return guest.CounterRead.parse(self.sh(sb, guest.counter_read(COUNTER_TAG)).stdout)

    def counter_continued(self, sb: Any, before: guest.CounterRead) -> Check:
        """The memory check: the same process and buffer, still counting, ≥ 2 s apart."""
        r1 = self.read_counter(sb)
        self.env.sleep(COUNTER_GAP_S)
        r2 = self.read_counter(sb)
        ident = (before.pid, before.start, before.cmdline)
        same = None not in ident[:2] and all((r.pid, r.start, r.cmdline) == ident for r in (r1, r2))
        v0, c1, c2 = before.counter, r1.counter, r2.counter
        counting = v0 is not None and c1 is not None and c2 is not None and v0 <= c1 < c2
        shm_kept = before.shm is not None and r1.shm == before.shm
        evidence: Evidence = {
            "pid": [before.pid, r1.pid, r2.pid],
            "start_time": [before.start, r1.start, r2.start],
            "cmdline_same": r1.cmdline == before.cmdline,
            "shm_sha256": [before.shm, r1.shm],
            "counter": [v0, c1, c2],
        }
        return Check(same and shm_kept and counting, evidence)

    def write_random(self, sb: Any, size: int = FILE_BYTES, name: str = "sbx-file") -> Written:
        return Written(name, guest.sha256(self.sh(sb, guest.write_random(name, size)).stdout))

    def file_hash(self, sb: Any, name: str) -> str | None:
        return guest.sha256(self.sh(sb, guest.hash_file(name)).stdout)

    def same_file(self, sb: Any, written: Written) -> Check:
        actual = self.file_hash(sb, written.name)
        ok = written.sha256 is not None and actual == written.sha256
        return Check(ok, {"expected_sha256": written.sha256, "actual_sha256": actual})


ActionFn = Callable[[Context], Mapping[str, Check]]


@dataclass(frozen=True, slots=True)
class Action:
    name: str
    fn: ActionFn
    verdicts: tuple[str, ...]
    timings: tuple[str, ...]


REGISTRY: dict[str, Action] = {}


def action(*, verdicts: Sequence[str], timings: Sequence[str]) -> Callable[[ActionFn], ActionFn]:
    """Register an action under its module's name, e.g. ``pause``."""

    def register(fn: ActionFn) -> ActionFn:
        name = fn.__module__.rsplit(".", 1)[-1]
        unknown = (set(verdicts) - set(PROBES)) | (set(timings) - TIMINGS)
        if unknown or name in REGISTRY:
            msg = f"bad action {name!r}: unknown {sorted(unknown)} or registered twice"
            raise ValueError(msg)
        REGISTRY[name] = Action(name, fn, tuple(verdicts), tuple(timings))
        return fn

    return register


def actions() -> list[Action]:
    """Every action, in ``MODULES`` order."""
    for module in MODULES:
        importlib.import_module(f"{__name__}.{module}")
    return [REGISTRY[m] for m in MODULES]
