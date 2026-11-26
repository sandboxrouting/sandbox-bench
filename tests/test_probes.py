"""Every probe passes against the fake provider, and fails when its feature is broken."""

from __future__ import annotations

import pytest

from sandbox_bench.benchmark import PROBES
from sandbox_bench.probes import REGISTRY, actions
from sandbox_bench.providers.fake import FAILURES, Fake
from sandbox_bench.runner import Run
from sandbox_bench.schema import Attempt


def run_probe(fake: Fake, probe: str) -> Attempt:
    (attempt,) = (
        Run([fake], attempts=1, seed=0, only=frozenset({probe}), strict=True).run().attempts
    )
    assert list(attempt.verdicts) == [probe]
    return attempt


def test_five_actions_cover_the_eleven_probes_once() -> None:
    names = [a.name for a in actions()]
    assert names == ["basics", "network", "pause", "snapshot", "fork"]
    assert sorted(p for a in REGISTRY.values() for p in a.verdicts) == sorted(PROBES)


def test_every_probe_has_a_failure_mode() -> None:
    assert set(FAILURES) == set(PROBES)


@pytest.mark.parametrize("probe", PROBES)
def test_probe_passes(probe: str) -> None:
    verdict = run_probe(Fake(), probe).verdicts[probe]
    assert verdict.outcome == "pass", verdict
    assert verdict.error is None


@pytest.mark.parametrize("probe", PROBES)
def test_probe_fails_when_broken(probe: str) -> None:
    fake = Fake(broken={probe})
    attempt = run_probe(fake, probe)
    assert attempt.verdicts[probe].outcome == "fail", FAILURES[probe]
    assert not fake.boxes
    assert not fake.snapshots


def test_broken_create_exec_times_out_and_records_no_start() -> None:
    attempt = run_probe(Fake(broken={"create-exec"}), "create-exec")
    error = attempt.verdicts["create-exec"].error or ""
    assert error.startswith("OperationTimeoutError: no command succeeded within 120 s")
    assert "start" not in attempt.timings


def test_memory_failure_evidence_shows_a_restart() -> None:
    attempt = run_probe(Fake(broken={"pause-keeps-memory"}), "pause-keeps-memory")
    evidence = attempt.verdicts["pause-keeps-memory"].evidence
    shm, counter = evidence["shm_sha256"], evidence["counter"]
    assert isinstance(shm, list)
    assert isinstance(counter, list)
    start = evidence["start_time"]
    assert isinstance(start, list)
    assert start[0]
    assert start[1:] == [None, None]
    assert shm[1] is None
    assert counter[1] == counter[2]  # the stale file no longer counts up


def test_files_only_pause_keeps_files() -> None:
    fake = Fake(broken={"pause-keeps-memory"})
    run = Run([fake], attempts=1, only=frozenset({"pause-keeps-files", "pause-keeps-memory"}))
    (attempt,) = run.run().attempts
    outcomes = {p: v.outcome for p, v in attempt.verdicts.items()}
    assert outcomes == {"pause-keeps-files": "pass", "pause-keeps-memory": "fail"}
    assert attempt.timings.keys() == {"start", "pause", "resume"}


def test_fork_timing_is_one_child_to_first_command() -> None:
    attempt = run_probe(Fake(), "fork-keeps-memory")
    assert attempt.timings["fork"] == pytest.approx(0.3 + 0.01)  # fork, then one echo


def test_unreachable_port_reports_the_error() -> None:
    attempt = run_probe(Fake(broken={"exposed-port"}), "exposed-port")
    verdict = attempt.verdicts["exposed-port"]
    assert (verdict.error or "").startswith("ConnectionRefusedError")
    assert verdict.evidence["server"] == "python3"


def test_a_broken_expose_port_fails_only_its_probe() -> None:
    fake = Fake(errors={"expose_port"})
    (attempt,) = (
        Run([fake], attempts=1, only=frozenset({"internet", "exposed-port"})).run().attempts
    )
    assert attempt.verdicts["internet"].outcome == "pass"
    assert attempt.verdicts["exposed-port"].outcome == "fail"
    assert attempt.verdicts["exposed-port"].evidence == {"op": "expose_port"}
