"""The columns and the scoring: run records in, ranked boards out (METHODOLOGY §2, §4, §5).

Pure functions, no I/O. Adding a column takes one line in ``COLUMNS``: the metric and the
probe that must pass for it to be shown.
"""

from __future__ import annotations

import statistics
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Final, Literal

from sandbox_bench.adapter import STANDARD_SIZE
from sandbox_bench.benchmark import ALWAYS_OFFERED, PASS_THRESHOLD, PROBES, VERSION, WINDOW
from sandbox_bench.schema import Attempt, Evidence, ProviderInfo, RunRecord

Status = Literal["pass", "failing", "n/a", "pending"]


@dataclass(frozen=True, slots=True)
class Column:
    title: str
    metric: str
    """Key in ``Attempt.timings``."""
    gate: str
    """The probe that must pass for the column to show a number."""
    state: bool = False
    """Ranks only providers at the standard size: memory size changes these timings."""
    main: bool = False
    """Shown in the main leaderboard table, not only in the per-metric tables."""


COLUMNS: Final = (
    Column("Start", "start", gate="create-exec", main=True),
    Column("Resume", "resume", gate="pause-keeps-files", state=True, main=True),
    Column("Restore", "restore", gate="snapshot-keeps-files", state=True, main=True),
    Column("Fork", "fork", gate="fork-keeps-memory", state=True, main=True),
    Column("Exec", "exec", gate="create-exec"),
    Column("Pause", "pause", gate="pause-keeps-files"),
    Column("Snapshot", "snapshot", gate="snapshot-keeps-files"),
)
BY_METRIC: Final = {c.metric: c for c in COLUMNS}

MEMORY: Final = {
    "pause": "pause-keeps-memory",
    "snapshot": "snapshot-keeps-memory",
    "fork": "fork-keeps-memory",
}
"""Keeps memory on: the operation, and the memory probe that must pass for it."""

FACTS: Final = (  # label, files probe, memory probe, timed metric
    ("Pause", "pause-keeps-files", "pause-keeps-memory", "pause"),
    ("Snapshot", "snapshot-keeps-files", "snapshot-keeps-memory", "snapshot"),
    ("Fork", None, "fork-keeps-memory", "fork"),
)

START_LABEL: Final = {"pool": "pool", "memory": "snapshot", "cold": "cold"}


def fmt_s(seconds: float) -> str:
    """Format a time like the README: "0.05 s", "0.9 s", "368 s"."""
    if seconds < 0.1:
        return f"{seconds:.2f} s"
    return f"{seconds:.1f} s" if seconds < 10 else f"{seconds:.0f} s"


def fmt_score(passed: int, total: int = len(PROBES)) -> str:
    """Format a score like "64% (7 of 11)", rounding half up."""
    return f"{(200 * passed + total) // (2 * total)}% ({passed} of {total})"


@dataclass(frozen=True, slots=True)
class Failure:
    """The latest failed attempt of a probe: where to find its evidence."""

    run_id: str
    action: str
    index: int
    started_at: datetime
    error: str | None
    evidence: Evidence


@dataclass(frozen=True, slots=True)
class ProbeResult:
    status: Status
    passed: int = 0
    counted: int = 0
    """Non-excluded attempts in the window (at most ``WINDOW``)."""
    last_failure: Failure | None = None


@dataclass(frozen=True, slots=True)
class Stat:
    p50: float
    p90: float
    n: int
    first: datetime
    last: datetime


@dataclass(frozen=True, slots=True)
class ProviderBoard:
    info: ProviderInfo
    probes: Mapping[str, ProbeResult]
    metrics: Mapping[str, Stat]
    """Every metric with samples, whether or not its gate passes; use ``shown``."""
    api_rtt: float | None

    def with_status(self, status: Status) -> list[str]:
        return [p for p in PROBES if self.probes[p].status == status]

    @property
    def passed(self) -> int:
        return len(self.with_status("pass"))

    @property
    def complete(self) -> bool:
        """Every probe has its 10 attempts, so the provider can be ranked."""
        return not self.with_status("pending")

    @property
    def standard_size(self) -> bool:
        size = self.info.size
        return (size.vcpu, size.memory_gib) == (STANDARD_SIZE.vcpu, STANDARD_SIZE.memory_gib)

    def keeps_memory(self) -> list[str]:
        return [op for op, probe in MEMORY.items() if self.probes[probe].status == "pass"]

    def shown(self, col: Column) -> Stat | None:
        """The column's stat, only when its gating probe passes."""
        return self.metrics.get(col.metric) if self.probes[col.gate].status == "pass" else None

    def blank(self, col: Column) -> str:
        """Why ``col`` shows no number: the gate's status, or "no samples"."""
        status = self.probes[col.gate].status
        return "no samples" if status == "pass" else status

    def ranked_in(self, col: Column) -> bool:
        stat = self.shown(col)
        return stat is not None and stat.n >= WINDOW and (self.standard_size or not col.state)

    def facts(self) -> str:
        """One plain line, e.g. "Start: cold, 1.6 s. Pause: not offered. Snapshot: files
        only, 368 s. Fork: not offered." """
        start = self.shown(BY_METRIC["start"])
        when = fmt_s(start.p50) if start else self.blank(BY_METRIC["start"])
        parts = [f"Start: {START_LABEL[self.info.start_mode]}, {when}"]
        parts += [f"{label}: {self._state(*row)}" for label, *row in FACTS]
        return ". ".join(parts) + "."

    def _state(self, files: str | None, memory: str, metric: str) -> str:
        status = {p: self.probes[p].status for p in (files, memory) if p}
        if set(status.values()) == {"n/a"}:
            return "not offered"
        if status[memory] == "pass":
            text = "keeps memory"
        elif files and status[files] == "pass":
            text = "files only"
        else:
            return "failing" if "failing" in status.values() else "pending"
        if stat := self.shown(BY_METRIC[metric]):
            text += f", {fmt_s(stat.p50)}"
        if mechanism := self.info.mechanisms.get(metric):
            text += f" ({mechanism})"
        return text


@dataclass(frozen=True, slots=True)
class Board:
    version: str
    run_ids: tuple[str, ...]
    runner_regions: tuple[str, ...]
    first: datetime | None
    """Earliest attempt counted in any window."""
    last: datetime | None
    providers: tuple[ProviderBoard, ...]
    """Ranked providers first, in rank order, then the ones with pending probes."""

    def rank(self, provider: ProviderBoard) -> int | None:
        ranked = [p for p in self.providers if p.complete]
        return ranked.index(provider) + 1 if provider.complete else None

    def column(self, col: Column) -> list[tuple[int | None, ProviderBoard, Stat]]:
        """Providers shown in ``col``: ranked ones by p50, then shown-but-unranked ones."""
        rows = sorted(
            ((p, s) for p in self.providers if (s := p.shown(col))),
            key=lambda ps: (not ps[0].ranked_in(col), ps[1].p50, ps[0].info.name),
        )
        ranked = [p for p, _ in rows if p.ranked_in(col)]
        return [(ranked.index(p) + 1 if p in ranked else None, p, s) for p, s in rows]


def check_version(records: Sequence[RunRecord]) -> None:
    """Refuse to score records from another benchmark version, or a mix (METHODOLOGY §8)."""
    versions = sorted({r.benchmark for r in records})
    if not versions:
        msg = "no run records to score"
        raise ValueError(msg)
    if len(versions) > 1:
        msg = f"can't mix benchmark versions {', '.join(versions)} in one report (METHODOLOGY §8)"
        raise ValueError(msg)
    if versions != [VERSION]:
        msg = f"records are benchmark {versions[0]}, but this harness scores {VERSION}"
        raise ValueError(msg)


def samples(attempts: Iterable[Attempt], col: Column) -> list[tuple[datetime, float]]:
    """Timing samples for ``col`` (METHODOLOGY §4): from attempts with no excluded verdict
    whose gate verdict, if any, passed. Start uses default creates only."""
    return [
        (a.started_at, a.timings[col.metric])
        for a in attempts
        if col.metric in a.timings
        and all(v.outcome != "excluded" for v in a.verdicts.values())
        and (a.default_create or col.metric != "start")
        and (col.gate not in a.verdicts or a.verdicts[col.gate].outcome == "pass")
    ]


def _stat(points: list[tuple[datetime, float]]) -> Stat:
    values = [v for _, v in points]
    p90 = (
        statistics.quantiles(values, n=10, method="inclusive")[8] if len(values) > 1 else values[0]
    )
    return Stat(statistics.median(values), p90, len(values), points[0][0], points[-1][0])


def _probe(
    probe: str, offered: bool, attempts: Sequence[tuple[str, Attempt]]
) -> tuple[ProbeResult, list[datetime]]:
    window = [
        (run_id, a, a.verdicts[probe])
        for run_id, a in attempts
        if probe in a.verdicts and a.verdicts[probe].outcome != "excluded"
    ][-WINDOW:]
    if not offered:
        return ProbeResult("n/a"), []
    passed = sum(v.outcome == "pass" for _, _, v in window)
    fails = [
        Failure(r, a.action, a.index, a.started_at, v.error, v.evidence)
        for r, a, v in window
        if v.outcome == "fail"
    ]
    status: Status = (
        "pending" if len(window) < WINDOW else "pass" if passed >= PASS_THRESHOLD else "failing"
    )
    result = ProbeResult(status, passed, len(window), fails[-1] if fails else None)
    return result, [a.started_at for _, a, _ in window]


def build(records: Sequence[RunRecord]) -> Board:
    """Merge run records in time order and score every provider (METHODOLOGY §5)."""
    check_version(records)
    records = sorted(records, key=lambda r: r.started_at)
    infos = {info.name: info for r in records for info in r.providers}  # latest wins
    attempts = sorted(
        ((r.run_id, a) for r in records for a in r.attempts),
        key=lambda ra: (ra[1].started_at, ra[0], ra[1].action, ra[1].index),
    )
    boards, used = [], []
    for name, info in infos.items():
        own = [(r, a) for r, a in attempts if a.provider == name]
        probes = {}
        for probe in PROBES:
            offered = probe in info.offers or probe in ALWAYS_OFFERED
            probes[probe], when = _probe(probe, offered, own)
            used += when
        metrics = {
            c.metric: _stat(pts[-WINDOW:])
            for c in COLUMNS
            if (pts := samples((a for _, a in own), c))
        }
        rtt = [x for r in records for x in r.api_rtt.get(name, [])][-WINDOW:]
        rtt_p50 = statistics.median(rtt) if rtt else None
        boards.append(ProviderBoard(info, probes, metrics, rtt_p50))
    start = BY_METRIC["start"]

    def order(p: ProviderBoard) -> tuple[bool, int, float, str]:
        stat = p.shown(start)
        return (not p.complete, -p.passed, stat.p50 if stat else float("inf"), p.info.name)

    return Board(
        version=records[0].benchmark,
        run_ids=tuple(r.run_id for r in records),
        runner_regions=tuple(dict.fromkeys(r.runner.region for r in records)),
        first=min(used, default=None),
        last=max(used, default=None),
        providers=tuple(sorted(boards, key=order)),
    )
