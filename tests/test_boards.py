"""Scoring edge cases (METHODOLOGY §2, §4, §5). The factories here are shared with
``test_report.py``."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import UTC, datetime, timedelta

import pytest

from sandbox_bench import boards
from sandbox_bench.benchmark import PROBES, VERSION
from sandbox_bench.boards import BY_METRIC, build, fmt_s, fmt_score
from sandbox_bench.schema import (
    Attempt,
    ProviderInfo,
    Runner,
    RunRecord,
    SizeRecord,
    Verdict,
)

T0 = datetime(2026, 11, 20, 6, 0, tzinfo=UTC)
DOCS = "https://docs.example.com/"
START, RESUME, FORK = BY_METRIC["start"], BY_METRIC["resume"], BY_METRIC["fork"]


def info(
    name: str = "alpha",
    offers: Sequence[str] = PROBES,
    *,
    size: tuple[float, float] = (2, 4),
    start_mode: str = "cold",
    plan: str = "free tier",
    mechanisms: Mapping[str, str] | None = None,
) -> ProviderInfo:
    return ProviderInfo.model_validate(
        {
            "name": name,
            "product": "vm",
            "owner": "@someone",
            "access": "sdk",
            "plan": plan,
            "region": "us-east-1",
            "start_mode": start_mode,
            "size": SizeRecord(vcpu=size[0], memory_gib=size[1]),
            "sdk": "",
            "offers": {p: DOCS + p for p in offers},
            "mechanisms": dict(mechanisms or {}),
        }
    )


def attempts(
    provider: str,
    n: int = 10,
    probes: Sequence[str] = PROBES,
    *,
    timings: Mapping[str, float] | None = None,
    fail: Mapping[str, int] | None = None,
    excluded: bool = False,
    default_create: bool = True,
    hour: int = 0,
) -> list[Attempt]:
    """``n`` attempts, an hour apart from ``T0 + hour``, each with a verdict for every probe in
    ``probes``. ``fail[probe]`` = how many of the *last* attempts fail that probe."""
    fail = fail or {}
    out = []
    for i in range(n):
        at = T0 + timedelta(hours=hour + i)
        verdicts = {}
        for p in probes:
            outcome = "fail" if i >= n - fail.get(p, 0) else "pass"
            if excluded:
                outcome = "excluded"
            evidence = {"expected": "abc", "actual": "xyz"} if outcome == "fail" else {}
            error = "AssertionError: hash mismatch" if outcome == "fail" else None
            verdicts[p] = Verdict(outcome=outcome, evidence=evidence, error=error)
        out.append(
            Attempt(
                provider=provider,
                action="all",
                index=i,
                started_at=at,
                finished_at=at + timedelta(minutes=1),
                verdicts=verdicts,
                timings=dict(timings or {}),
                default_create=default_create,
            )
        )
    return out


def record(
    providers: Sequence[ProviderInfo],
    atts: Sequence[Attempt],
    *,
    run_id: str = "r1",
    benchmark: str = VERSION,
    day: int = 0,
    api_rtt: Mapping[str, list[float]] | None = None,
) -> RunRecord:
    return RunRecord(
        benchmark=benchmark,
        run_id=run_id,
        harness_version="0.1.0",
        runner=Runner(region="us-east"),
        started_at=T0 + timedelta(days=day),
        finished_at=T0 + timedelta(days=day, hours=1),
        providers=list(providers),
        attempts=list(atts),
        api_rtt=dict(api_rtt or {}),
    )


def one(name: str = "alpha", **kw: object) -> boards.ProviderBoard:
    """Board of a single provider offering everything, with 10 attempts built from ``kw``."""
    board = build([record([info(name)], attempts(name, **kw))])  # type: ignore[arg-type]
    return board.providers[0]


# ---- formatting -------------------------------------------------------------------------------
@pytest.mark.parametrize(
    ("seconds", "text"),
    [(0.031, "0.03 s"), (0.9, "0.9 s"), (1.14, "1.1 s"), (9.94, "9.9 s"), (368.2, "368 s")],
)
def test_fmt_s(seconds: float, text: str) -> None:
    assert fmt_s(seconds) == text


@pytest.mark.parametrize(("passed", "text"), [(7, "64% (7 of 11)"), (6, "55% (6 of 11)")])
def test_fmt_score(passed: int, text: str) -> None:
    assert fmt_score(passed) == text


# ---- probe outcomes ---------------------------------------------------------------------------
def test_all_pass() -> None:
    p = one(timings={"start": 1.0})
    assert p.passed == 11
    assert p.complete
    assert p.probes["create-exec"] == boards.ProbeResult("pass", 10, 10)


def test_one_failure_in_ten_still_passes_two_fail() -> None:
    p = one(fail={"internet": 1, "egress-block": 2})
    assert p.probes["internet"].status == "pass"
    assert p.probes["egress-block"].status == "failing"
    assert p.with_status("failing") == ["egress-block"]
    failure = p.probes["egress-block"].last_failure
    assert failure is not None
    assert (failure.run_id, failure.index, failure.error) == (
        "r1",
        9,
        "AssertionError: hash mismatch",
    )


def test_not_offered_is_na_even_with_attempts_and_counts_zero() -> None:
    board = build([record([info("alpha", ["create-exec"])], attempts("alpha"))])
    p = board.providers[0]
    assert p.probes["pause-keeps-files"].status == "n/a"
    assert p.probes["file-roundtrip"].status == "pass"  # always offered
    assert p.passed == 2


def test_fewer_than_ten_attempts_is_pending_and_unranked() -> None:
    full = attempts("alpha", timings={"start": 2.0})
    short = attempts("beta", 9, timings={"start": 0.1})
    board = build([record([info("beta"), info("alpha")], full + short)])
    assert [p.info.name for p in board.providers] == ["alpha", "beta"]
    beta = board.providers[1]
    assert beta.probes["create-exec"] == boards.ProbeResult("pending", 9, 9)
    assert not beta.complete
    assert board.rank(board.providers[0]) == 1
    assert board.rank(beta) is None
    assert beta.shown(START) is None


def test_window_is_the_last_ten() -> None:
    old = attempts("alpha", 5, fail={"internet": 5})
    new = attempts("alpha", 10, hour=10)
    p = build([record([info()], old + new)]).providers[0]
    assert p.probes["internet"] == boards.ProbeResult("pass", 10, 10)


def test_excluded_attempts_are_ignored() -> None:
    good = attempts("alpha", timings={"start": 1.0})
    ours = attempts("alpha", 3, excluded=True, timings={"start": 99.0}, hour=20)
    p = build([record([info()], good + ours)]).providers[0]
    assert p.probes["create-exec"] == boards.ProbeResult("pass", 10, 10)
    assert p.metrics["start"].p50 == 1.0
    assert p.metrics["start"].n == 10


# ---- timings and columns ----------------------------------------------------------------------
def test_gating_hides_time() -> None:
    p = one(fail={"create-exec": 2}, timings={"start": 1.0, "resume": 0.3})
    assert p.metrics["start"].n == 8  # failed attempts never become samples
    assert p.shown(START) is None
    assert p.shown(RESUME) is not None


def test_p50_p90_over_last_ten_samples() -> None:
    early = attempts("alpha", 5, timings={"start": 50.0})
    late = [
        a.model_copy(update={"timings": {"start": float(i + 1)}})
        for i, a in enumerate(attempts("alpha", 10, hour=5))
    ]
    stat = build([record([info()], early + late)]).providers[0].metrics["start"]
    assert (stat.p50, stat.n, stat.first) == (5.5, 10, T0 + timedelta(hours=5))
    assert stat.p90 == pytest.approx(9.1)


def test_start_uses_default_creates_only() -> None:
    plain = attempts("alpha", timings={"start": 1.0})
    egress = attempts("alpha", 10, ["egress-block"], timings={"start": 0.1}, default_create=False)
    p = build([record([info()], plain + egress)]).providers[0]
    assert p.metrics["start"].p50 == 1.0


def test_ties_go_to_faster_start() -> None:
    slow = attempts("alpha", timings={"start": 2.0})
    fast = attempts("beta", timings={"start": 1.0})
    board = build([record([info("alpha"), info("beta")], slow + fast)])
    assert [(board.rank(p), p.info.name) for p in board.providers] == [(1, "beta"), (2, "alpha")]


def test_score_beats_start() -> None:
    fast = attempts("alpha", timings={"start": 0.1}, fail={"internet": 5})
    slow = attempts("beta", timings={"start": 3.0})
    board = build([record([info("alpha"), info("beta")], fast + slow)])
    assert [p.info.name for p in board.providers] == ["beta", "alpha"]


def test_fewer_than_ten_samples_is_shown_but_not_ranked() -> None:
    timed = attempts("alpha", 9, timings={"resume": 0.5})
    untimed = attempts("alpha", 1, hour=9)
    p = build([record([info()], timed + untimed)]).providers[0]
    assert p.probes["pause-keeps-files"].status == "pass"
    assert p.shown(RESUME) is not None
    assert not p.ranked_in(RESUME)
    board = build([record([info()], timed + untimed)])
    assert [(r, q.info.name) for r, q, _ in board.column(RESUME)] == [(None, "alpha")]


def test_non_standard_size_is_not_ranked_on_state_columns() -> None:
    big = attempts("big", timings={"start": 1.0, "resume": 0.1})
    std = attempts("std", timings={"start": 2.0, "resume": 0.9})
    board = build([record([info("big", size=(2, 8)), info("std")], big + std)])
    ranks = {c.metric: [(r, p.info.name) for r, p, _ in board.column(c)] for c in (START, RESUME)}
    assert ranks["start"] == [(1, "big"), (2, "std")]
    assert ranks["resume"] == [(1, "std"), (None, "big")]


def test_keeps_memory_and_facts() -> None:
    offers = ["create-exec", "snapshot-keeps-files", "snapshot-keeps-memory", "fork-keeps-memory"]
    atts = attempts(
        "alpha",
        timings={"start": 1.6, "snapshot": 368.0, "fork": 2.0},
        fail={"fork-keeps-memory": 3},
    )
    p = build([record([info("alpha", offers)], atts)]).providers[0]
    assert p.probes["snapshot-keeps-memory"].status == "pass"
    assert p.keeps_memory() == ["snapshot"]
    assert p.facts() == (
        "Start: cold, 1.6 s. Pause: not offered. Snapshot: keeps memory, 368 s. Fork: failing."
    )


def test_facts_files_only_and_pending() -> None:
    offers = ["create-exec", "pause-keeps-files", "snapshot-keeps-files", "fork-keeps-memory"]
    probes = ["create-exec", "file-roundtrip", "pause-keeps-files", "snapshot-keeps-files"]
    full = attempts("alpha", 10, probes, timings={"start": 1.0, "snapshot": 368.0})
    late = attempts("alpha", 9, ["fork-keeps-memory"], timings={"fork": 1.1}, hour=10)
    pr = info("alpha", offers, start_mode="memory")
    p = build([record([pr], full + late)]).providers[0]
    assert p.facts() == (
        "Start: snapshot, 1.0 s. Pause: files only. Snapshot: files only, 368 s. Fork: pending."
    )


def test_facts_show_mechanism_and_failing_start() -> None:
    pr = info("alpha", ["create-exec", "fork-keeps-memory"], mechanisms={"fork": "snapshot + N"})
    atts = attempts("alpha", timings={"start": 1.0, "fork": 1.1}, fail={"create-exec": 2})
    p = build([record([pr], atts)]).providers[0]
    assert p.facts() == (
        "Start: cold, failing. Pause: not offered. Snapshot: not offered."
        " Fork: keeps memory, 1.1 s (snapshot + N)."
    )


# ---- merging records --------------------------------------------------------------------------
def test_records_merge_in_time_order_and_latest_info_wins() -> None:
    day1 = record([info(plan="free tier")], attempts("alpha", 5, fail={"internet": 5}), run_id="d1")
    day2 = record([info(plan="pro")], attempts("alpha", 5, hour=24), run_id="d2", day=1)
    day3 = record([info(plan="pro")], attempts("alpha", 5, hour=48), run_id="d3", day=2)
    board = build([day3, day1, day2])
    p = board.providers[0]
    assert board.run_ids == ("d1", "d2", "d3")
    assert p.info.plan == "pro"
    assert p.probes["internet"] == boards.ProbeResult("pass", 10, 10)
    assert board.first == T0 + timedelta(hours=24)


def test_api_rtt_median_of_last_ten() -> None:
    rec = record([info()], attempts("alpha"), api_rtt={"alpha": [9.0] * 5 + [0.1] * 10})
    assert build([rec]).providers[0].api_rtt == 0.1
    assert build([record([info()], attempts("alpha"))]).providers[0].api_rtt is None


@pytest.mark.parametrize(
    ("versions", "message"),
    [
        ([], "no run records"),
        (["v0.0", VERSION], "mix benchmark versions v0.0, v0.1 in one report"),
        (["v0.0"], "records are benchmark v0.0, but this harness scores v0.1"),
    ],
)
def test_versions_are_never_mixed(versions: list[str], message: str) -> None:
    recs = [record([info()], [], benchmark=v, run_id=f"r{i}") for i, v in enumerate(versions)]
    with pytest.raises(ValueError, match=message):
        build(recs)
