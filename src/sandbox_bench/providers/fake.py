"""Offline provider: used by the tests, and by ``sbx run --providers fake`` to try the harness.

Each sandbox is an in-memory model (files, a ``/dev/shm`` buffer, the counter process) on a
virtual clock, so the 2 s memory-check gap costs nothing. The fake recognises the harness's
guest scripts by their ``# sbx:<kind>`` header and answers the way a real sandbox would.

By default it passes every probe. Each probe can be broken with a realistic failure mode
(``FAILURES``), and any operation can be made to hang, fail or hit an account error::

    Fake(broken={"pause-keeps-memory"})  # pause keeps files only: resume reboots
    Fake(hang={"snapshot"}, timeouts={**TIMEOUTS, "snapshot": 0.05})
    Fake(account_errors={"create"})
"""

from __future__ import annotations

import copy
import hashlib
import random
import threading
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from itertools import count
from typing import ClassVar, Final

from sandbox_bench.adapter import AccountError, Adapter, Endpoint, ExecResult, Spec
from sandbox_bench.benchmark import COUNTER_INTERVAL_S, PROBES, TIMEOUTS
from sandbox_bench.harness import Env
from sandbox_bench.probes import guest

FAILURES: Final = {
    "create-exec": "echo prints nothing",
    "file-roundtrip": "files read back corrupted",
    "internet": "downloads come back with the wrong bytes",
    "egress-block": "outbound traffic isn't blocked",
    "exposed-port": "the exposed URL is unreachable",
    "pause-keeps-files": "resume comes back with an empty disk",
    "pause-keeps-memory": "pause keeps files only: resume reboots",
    "snapshot-keeps-files": "restore comes back with an empty disk",
    "snapshot-keeps-memory": "snapshots keep files only: restore boots fresh",
    "fork-keeps-memory": "forks copy files only: children boot fresh",
    "fork-isolation-x3": "forks share one filesystem",
}
LATENCY_S: Final = {"create": 0.4, "restore": 0.3, "resume": 0.2, "fork": 0.3, "snapshot": 1.0}
"""Virtual time each operation takes, so recorded timings are deterministic and non-zero."""


class VirtualClock:
    def __init__(self) -> None:
        self.t = 0.0

    def now(self) -> float:
        return self.t

    def sleep(self, seconds: float) -> None:
        self.t += seconds


def _sha(content: str) -> str:
    return hashlib.sha256(content.encode()).hexdigest()


@dataclass
class Proc:
    """The counter loop: counts up every 0.5 s of virtual time unless frozen by a pause."""

    pid: int
    start: int
    cmdline: str
    value0: int
    t0: float
    frozen_at: float | None = None

    def value(self, now: float) -> int:
        at = now if self.frozen_at is None else self.frozen_at
        return self.value0 + int((at - self.t0) / COUNTER_INTERVAL_S)


@dataclass
class FakeSandbox:
    name: str
    egress: bool
    boot_id: str
    booted_at: float
    files: dict[str, str] = field(default_factory=dict)
    shm: dict[str, str] = field(default_factory=dict)
    procs: dict[int, Proc] = field(default_factory=dict)
    served: dict[int, str] = field(default_factory=dict)
    paused: bool = False


@dataclass
class FakeSnapshot:
    name: str
    state: FakeSandbox


class Fake(Adapter[FakeSandbox, FakeSnapshot]):
    name = "fake"
    product = "simulated"
    owner = "@sandboxrouting"
    access = "sdk"
    plan = "offline"
    region = "local"
    start_mode = "memory"
    offers: ClassVar[Mapping[str, str]] = {p: f"https://example.com/fake#{p}" for p in PROBES}
    mechanisms: ClassVar[Mapping[str, str]] = {"fork": "in-memory copy"}

    def __init__(
        self,
        broken: Iterable[str] = (),
        *,
        hang: Iterable[str] = (),
        errors: Iterable[str] = (),
        account_errors: Iterable[str] = (),
        timeouts: Mapping[str, float] = TIMEOUTS,
    ) -> None:
        self.broken = frozenset(broken)
        unknown = self.broken - set(FAILURES)
        if unknown:
            raise ValueError(f"no failure mode for {sorted(unknown)}")
        self.hang, self.errors = frozenset(hang), frozenset(errors)
        self.account_errors = frozenset(account_errors)
        self.clock = VirtualClock()
        self.simulated_env = Env(self.clock.now, self.clock.sleep, self.http_get, timeouts)
        self.release = threading.Event()
        """Set it to let hung operations finish (tests do, so no thread outlives them)."""
        self.boxes: dict[str, FakeSandbox] = {}
        self.snapshots: dict[str, FakeSnapshot] = {}
        self.calls: list[str] = []
        self._rng = random.Random(0)  # noqa: S311 - deterministic test data, not crypto
        self._pids = count(100)

    # ---- the operation hook: latency, hangs, injected errors ---------------------------------
    def _op(self, op: str) -> None:
        self.calls.append(op)
        if op in self.account_errors:
            raise AccountError(f"{op}: credits exhausted")
        if op in self.errors:
            raise RuntimeError(f"{op}: HTTP 500 from the fake API")
        if op in self.hang:
            self.release.wait(30)
        self.clock.sleep(LATENCY_S.get(op, 0.01))

    def _hex(self) -> str:
        return f"{self._rng.getrandbits(128):032x}"

    def _new_box(self, name: str, egress: bool) -> FakeSandbox:
        sb = FakeSandbox(name, egress, self._hex(), self.clock.now())
        self.boxes[name] = sb
        return sb

    def _reboot(self, sb: FakeSandbox, *, wipe_disk: bool = False) -> None:
        """What a files-only resume or restore looks like from inside: a new boot."""
        for tag, pid in [
            (k.removesuffix(".pid"), v) for k, v in sb.files.items() if k.endswith(".pid")
        ]:
            if (proc := sb.procs.get(int(pid))) is not None:
                sb.files[f"{tag}.counter"] = str(proc.value(self.clock.now()))  # left stale
        sb.procs, sb.shm, sb.served = {}, {}, {}
        sb.boot_id, sb.booted_at = self._hex(), self.clock.now()
        if wipe_disk:
            sb.files = {}

    def _copy(self, state: FakeSandbox, spec: Spec) -> FakeSandbox:
        """A memory copy: the counter carries on from its value at copy time."""
        sb = copy.deepcopy(state)
        sb.name, sb.egress, sb.paused = spec.name, spec.egress, False
        for proc in sb.procs.values():
            proc.value0, proc.t0, proc.frozen_at = (
                proc.value(self.clock.now()),
                self.clock.now(),
                None,
            )
        self.boxes[spec.name] = sb
        return sb

    # ---- required ----------------------------------------------------------------------------
    def create(self, spec: Spec) -> FakeSandbox:
        self._op("create")
        return self._new_box(spec.name, spec.egress)

    def exec(self, sb: FakeSandbox, cmd: str, timeout_s: float) -> ExecResult:
        self._op("exec")
        if sb.name not in self.boxes or sb.paused:
            raise RuntimeError(f"sandbox {sb.name} is {'paused' if sb.paused else 'gone'}")
        if cmd.startswith("echo "):
            return ExecResult(0, "\n" if "create-exec" in self.broken else cmd[5:] + "\n")
        if cmd == "true":
            return ExecResult(0, "")
        found = guest.identify(cmd)
        if found is None:
            return ExecResult(127, "", "sh: not found\n")
        kind, args = found
        lines = getattr(self, f"_sh_{kind.replace('-', '_')}")(sb, **args)
        return ExecResult(0, "".join(f"{line}\n" for line in lines))

    def destroy(self, sb: FakeSandbox) -> None:
        self._op("destroy")
        self.boxes.pop(sb.name, None)

    # ---- optional ----------------------------------------------------------------------------
    def pause(self, sb: FakeSandbox) -> None:
        self._op("pause")
        sb.paused = True
        for proc in sb.procs.values():
            proc.frozen_at = self.clock.now()

    def resume(self, sb: FakeSandbox) -> None:
        self._op("resume")
        sb.paused = False
        for proc in sb.procs.values():
            if proc.frozen_at is not None:
                proc.t0 += self.clock.now() - proc.frozen_at
                proc.frozen_at = None
        if self.broken & {"pause-keeps-memory", "pause-keeps-files"}:
            self._reboot(sb, wipe_disk="pause-keeps-files" in self.broken)

    def snapshot(self, sb: FakeSandbox, name: str) -> FakeSnapshot:
        self._op("snapshot")
        snap = FakeSnapshot(name, copy.deepcopy(sb))
        self.snapshots[name] = snap
        return snap

    def restore(self, snap: FakeSnapshot, spec: Spec) -> FakeSandbox:
        self._op("restore")
        sb = self._copy(snap.state, spec)
        if self.broken & {"snapshot-keeps-memory", "snapshot-keeps-files"}:
            self._reboot(sb, wipe_disk="snapshot-keeps-files" in self.broken)
        return sb

    def delete_snapshot(self, snap: FakeSnapshot) -> None:
        self._op("delete_snapshot")
        self.snapshots.pop(snap.name, None)

    def fork(self, sb: FakeSandbox, specs: Sequence[Spec]) -> list[FakeSandbox]:
        self._op("fork")
        children = [self._copy(sb, spec) for spec in specs]
        for child in children:
            if "fork-keeps-memory" in self.broken:
                self._reboot(child)
            if "fork-isolation-x3" in self.broken:
                child.files = sb.files
        return children

    def expose_port(self, sb: FakeSandbox, port: int) -> Endpoint:
        self._op("expose_port")
        return Endpoint(f"fake://{sb.name}:{port}/", {"x-fake-token": "secret"})

    def ping(self) -> None:
        self._op("ping")

    def reap(self, prefix: str) -> int:
        self._op("reap")
        doomed = [n for n in self.boxes if n.startswith(prefix)]
        doomed += [n for n in self.snapshots if n.startswith(prefix)]
        for name in doomed:
            self.boxes.pop(name, None)
            self.snapshots.pop(name, None)
        return len(doomed)

    # ---- the simulated network, used through ``simulated_env`` -------------------------------
    def http_get(self, endpoint: Endpoint) -> str:
        name, _, port = endpoint.url.removeprefix("fake://").rstrip("/").rpartition(":")
        sb = self.boxes.get(name)
        token = sb.served.get(int(port)) if sb else None
        if token is None or "exposed-port" in self.broken:
            raise ConnectionRefusedError(f"connection refused: {endpoint.url}")
        return token

    # ---- guest scripts, by kind --------------------------------------------------------------
    def _sh_counter_start(self, sb: FakeSandbox, tag: str) -> list[str]:
        pid = next(self._pids)
        start = int((self.clock.now() - sb.booted_at) * 100)
        cmdline = f"sh -c <loop> sbx-counter /root/.sbx/{tag}"
        sb.procs[pid] = Proc(pid, start, cmdline, 1, self.clock.now())
        sb.shm[tag] = self._hex()
        sb.files[f"{tag}.pid"] = str(pid)
        return self._sh_counter_read(sb, tag)

    def _sh_counter_read(self, sb: FakeSandbox, tag: str) -> list[str]:
        pid = sb.files.get(f"{tag}.pid", "")
        proc = sb.procs.get(int(pid)) if pid else None
        shm = _sha(sb.shm[tag]) if tag in sb.shm else ""
        if proc is None:
            return [f"pid={pid}", f"shm={shm}", f"counter={sb.files.get(f'{tag}.counter', '')}"]
        counter = proc.value(self.clock.now())
        return [
            f"pid={pid}",
            f"start={proc.start}",
            f"cmdline={proc.cmdline}",
            f"shm={shm}",
            f"counter={counter}",
        ]

    def _sh_write(self, sb: FakeSandbox, name: str, size: str) -> list[str]:
        sb.files[name] = f"{size}:{self._hex()}"
        return [f"sha256={_sha(sb.files[name])}"]

    def _sh_hash(self, sb: FakeSandbox, name: str) -> list[str]:
        content = sb.files.get(name)
        if content is not None and "file-roundtrip" in self.broken:
            content += "-bitrot"
        return [f"sha256={_sha(content) if content is not None else ''}"]

    def _sh_boot(self, sb: FakeSandbox) -> list[str]:
        return [f"uptime={self.clock.now() - sb.booted_at:.2f}", f"boot_id={sb.boot_id}"]

    def _sh_serve(self, sb: FakeSandbox, port: str, token: str) -> list[str]:
        sb.served[int(port)] = token
        return ["server=python3"]

    def _sh_download(self, sb: FakeSandbox, url: str) -> list[str]:
        if not sb.egress:
            return ["rc=6", "tool=curl", "sha256="]
        ok = url == guest.PINNED_URL and "internet" not in self.broken
        return ["rc=0", "tool=curl", f"sha256={guest.PINNED_SHA256 if ok else _sha(url)}"]

    def _sh_egress(self, sb: FakeSandbox, targets: str) -> list[str]:
        open_ = sb.egress or "egress-block" in self.broken
        rcs = [f"rc{n}={0 if open_ else 8}" for n in range(1, len(targets.split(",")) + 1)]
        return ["tool=python3", *rcs]
