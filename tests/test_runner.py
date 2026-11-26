"""Runner and harness properties: order, timeouts, errors, cleanup, pacing, the record."""

from __future__ import annotations

import re
from collections.abc import Iterator, Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import ClassVar

import httpx
import pytest

from sandbox_bench import probes
from sandbox_bench.adapter import Adapter, Endpoint, Spec
from sandbox_bench.benchmark import TIMEOUTS
from sandbox_bench.harness import Env, OperationTimeoutError, Pacer, http_get, with_deadline
from sandbox_bench.probes import REGISTRY, Context
from sandbox_bench.providers.fake import Fake, FakeSandbox
from sandbox_bench.runner import Run, git_sha, new_run_id, wanted, write_record
from sandbox_bench.schema import RunRecord

PAUSE = frozenset({"pause-keeps-files", "pause-keeps-memory"})


@pytest.fixture
def fake() -> Iterator[Fake]:
    adapter = Fake()
    yield adapter
    adapter.release.set()


def order(record: RunRecord) -> list[tuple[str, int]]:
    return [(a.action, a.index) for a in record.attempts]


def test_full_run_passes_everything_and_round_trips(fake: Fake) -> None:
    record = Run([fake], attempts=2, seed=1, strict=True, region="eu-west").run()
    assert len(record.attempts) == 2 * 5
    assert all(v.outcome == "pass" for a in record.attempts for v in a.verdicts.values())
    assert record.runner.region == "eu-west"
    assert len(record.api_rtt["fake"]) == 2
    assert record.log == []
    assert RunRecord.model_validate_json(record.model_dump_json()) == record
    assert not fake.boxes
    assert not fake.snapshots


def test_shuffle_is_seedable() -> None:
    def run(seed: int) -> list[tuple[str, int]]:
        return order(Run([Fake()], attempts=3, seed=seed, strict=True).run())

    assert run(7) == run(7)
    assert run(7) != run(8)
    assert order(Run([Fake()], attempts=3, seed=7).run()) != sorted(run(7))


def test_shuffle_interleaves_providers() -> None:
    class Other(Fake):
        name = "other"

    record = Run([Fake(), Other()], attempts=2, seed=3, strict=True).run()
    providers = [a.provider for a in record.attempts]
    assert providers != sorted(providers)
    assert [p.name for p in record.providers] == ["fake", "other"]


def test_warm_up_is_not_counted(fake: Fake) -> None:
    record = Run([fake], attempts=1, only=frozenset({"create-exec"}), strict=True).run()
    assert [a.action for a in record.attempts] == ["basics"]
    assert fake.calls.count("create") == 2  # warm-up, then the attempt


def test_resource_names(fake: Fake, monkeypatch: pytest.MonkeyPatch) -> None:
    names: list[str] = []
    real_create = fake.create

    def create(spec: Spec) -> FakeSandbox:
        names.append(spec.name)
        return real_create(spec)

    monkeypatch.setattr(fake, "create", create)
    record = Run([fake], attempts=1, strict=True).run()
    assert re.fullmatch(r"\d{8}-\d{6}-[0-9a-f]{4}", record.run_id)
    assert all(n.startswith(f"sbx-{record.run_id}-") for n in names)
    assert all(re.fullmatch(r"[a-z0-9]+(-[a-z0-9]+)*", n) and len(n) <= 63 for n in names)
    assert len(set(names)) == len(names)


def test_only_offered_probes_run() -> None:
    class Partial(Fake):
        offers: ClassVar[Mapping[str, str]] = {"pause-keeps-files": "https://example.com/pause"}

    record = Run([Partial()], attempts=1, strict=True).run()
    verdicts = {p for a in record.attempts for p in a.verdicts}
    assert verdicts == {"create-exec", "file-roundtrip", "pause-keeps-files"}
    assert wanted(Partial(), REGISTRY["network"]) == []


def test_egress_denied_create_is_not_a_default_create(fake: Fake) -> None:
    (attempt,) = (
        Run([fake], attempts=1, only=frozenset({"egress-block"}), strict=True).run().attempts
    )
    assert attempt.verdicts["egress-block"].outcome == "pass"
    assert attempt.default_create is False
    assert "start" in attempt.timings


def test_timeout_is_a_failure_not_a_sample() -> None:
    fake = Fake(hang={"pause"}, timeouts={**TIMEOUTS, "pause": 0.05})
    try:
        (attempt,) = Run([fake], attempts=1, only=PAUSE, strict=True).run().attempts
    finally:
        fake.release.set()
    assert {v.outcome for v in attempt.verdicts.values()} == {"fail"}
    error = attempt.verdicts["pause-keeps-files"].error
    assert error == "OperationTimeoutError: pause did not finish within 0.05 s"
    assert attempt.verdicts["pause-keeps-files"].evidence == {"op": "pause"}
    assert "pause" not in attempt.timings
    assert not fake.boxes


def test_account_error_is_excluded_and_logged() -> None:
    fake = Fake(account_errors={"snapshot"})
    record = Run([fake], attempts=1, only=frozenset({"snapshot-keeps-files"}), strict=True).run()
    (attempt,) = record.attempts
    verdict = attempt.verdicts["snapshot-keeps-files"]
    assert (verdict.outcome, verdict.error) == (
        "excluded",
        "AccountError: snapshot: credits exhausted",
    )
    assert record.log == ["fake snapshot#0: excluded: AccountError: snapshot: credits exhausted"]
    assert not fake.boxes


def test_provider_error_is_a_failure_with_its_type() -> None:
    record = Run([Fake(errors={"fork"})], attempts=1, only=frozenset({"fork-keeps-memory"})).run()
    verdict = record.attempts[0].verdicts["fork-keeps-memory"]
    assert verdict.outcome == "fail"
    assert verdict.error == "RuntimeError: fork: HTTP 500 from the fake API"


def test_harness_bug_crashes_in_strict_mode(monkeypatch: pytest.MonkeyPatch) -> None:
    def bug(*_: object) -> None:
        raise KeyError("oops")

    monkeypatch.setattr(Context, "write_random", bug)
    fake = Fake()
    with pytest.raises(KeyError):
        Run([fake], attempts=1, only=frozenset({"file-roundtrip"}), strict=True).run()
    assert not fake.boxes  # cleaned up on the way out


def test_harness_bug_is_excluded_otherwise(monkeypatch: pytest.MonkeyPatch) -> None:
    def bug(*_: object) -> None:
        raise KeyError("oops")

    monkeypatch.setattr(Context, "write_random", bug)
    record = Run([Fake()], attempts=1, only=frozenset({"file-roundtrip"})).run()
    verdict = record.attempts[0].verdicts["file-roundtrip"]
    assert (verdict.outcome, verdict.error) == ("excluded", "HarnessError: KeyError: 'oops'")
    assert record.log[0].endswith("excluded: HarnessError: KeyError: 'oops'")


def test_cleanup_failure_is_logged(fake: Fake) -> None:
    broken = Fake(errors={"destroy", "delete_snapshot"})
    record = Run([broken], attempts=1, only=frozenset({"snapshot-keeps-files"})).run()
    assert record.attempts[0].verdicts["snapshot-keeps-files"].outcome == "pass"
    assert any("cleanup destroy failed: RuntimeError" in line for line in record.log)
    assert any("cleanup delete_snapshot failed" in line for line in record.log)
    assert any("reaped" in line for line in record.log)  # the reaper caught the leftovers


def test_pacing_is_outside_the_clock() -> None:
    class Paced(Fake):
        pacing_s = 5.0

    only = frozenset({"create-exec"})
    paced, plain = Paced(), Fake()
    (slow,) = Run([paced], attempts=1, only=only, strict=True).run().attempts
    (fast,) = Run([plain], attempts=1, only=only, strict=True).run().attempts
    assert slow.timings == fast.timings
    assert paced.clock.now() > plain.clock.now() + 5 * 10


def test_pacer_waits_only_the_remaining_gap() -> None:
    fake = Fake()
    env = fake.simulated_env
    pacer = Pacer(2.0, env)
    pacer.wait()
    fake.clock.sleep(0.5)
    pacer.wait()
    assert pacer.waited == pytest.approx(1.5)


def test_reaper_runs_before_and_after() -> None:
    fake = Fake()
    fake.create(Spec("sbx-leftover"))
    record = Run([fake], attempts=1, only=frozenset({"create-exec"})).run()
    assert record.log == ["fake: reaped 1 leftover resources before the run"]
    assert fake.calls.count("reap") == 2


def test_reap_problems_are_logged() -> None:
    class NoReap(Fake):
        reap = Adapter.reap

    failing = Run([Fake(errors={"reap"})], attempts=1, only=frozenset({"create-exec"})).run()
    assert (
        failing.log[0]
        == "fake: reap before run failed: RuntimeError: reap: HTTP 500 from the fake API"
    )
    absent = Run([NoReap()], attempts=1, only=frozenset({"create-exec"})).run()
    assert absent.log[0] == "fake: no reaper; leftovers aren't cleaned up"


def test_warm_up_and_ping_failures_are_logged() -> None:
    record = Run(
        [Fake(errors={"create", "ping"})], attempts=1, only=frozenset({"create-exec"})
    ).run()
    assert "fake: warm-up failed: RuntimeError: create: HTTP 500 from the fake API" in record.log
    assert any(line.startswith("fake: ping failed") for line in record.log)
    assert record.api_rtt == {}
    assert record.attempts[0].verdicts["create-exec"].outcome == "fail"


def test_fork_with_the_wrong_number_of_children_fails() -> None:
    class Short(Fake):
        def fork(self, sb: FakeSandbox, specs: Sequence[Spec]) -> list[FakeSandbox]:
            return super().fork(sb, specs)[:1]

    fake = Short()
    (attempt,) = Run([fake], attempts=1, only=frozenset({"fork-isolation-x3"})).run().attempts
    assert attempt.verdicts["fork-isolation-x3"].error == "ValueError: asked for 3 children, got 1"
    assert not fake.boxes


def test_undeclared_timing_is_a_harness_bug(fake: Fake) -> None:
    env = fake.simulated_env
    h = Context(fake, prefix="sbx-t", wanted=(), timings=["start"], env=env, pacer=Pacer(0, env))
    with pytest.raises(ValueError, match="isn't declared"):
        h.timed("pause", lambda: None)


def test_with_deadline() -> None:
    def own_timeout() -> None:
        raise TimeoutError("the adapter's own")

    with pytest.raises(TimeoutError, match="the adapter's own") as info:
        with_deadline(own_timeout, [], 5, "exec")
    assert type(info.value) is TimeoutError
    assert with_deadline(lambda x: x + 1, [1], 5, "exec") == 2
    with pytest.raises(OperationTimeoutError):
        with_deadline(lambda: Fake().release.wait(1), [], 0.01, "exec")


def test_write_record_layout(tmp_path: Path, fake: Fake) -> None:
    record = Run([fake], attempts=1, only=frozenset({"create-exec"}), run_id="r1").run()
    path = write_record(record, tmp_path)
    assert path == tmp_path / f"{record.started_at:%Y/%m/%d}" / "r1.json"
    assert RunRecord.model_validate_json(path.read_text()) == record


def test_run_ids_and_git_sha() -> None:
    assert new_run_id(datetime(2026, 1, 2, 3, 4, 5, tzinfo=UTC)).startswith("20260102-030405-")
    sha = git_sha()
    assert sha is None or re.fullmatch(r"[0-9a-f]{40}", sha)


def test_counter_tag_is_shared_with_the_fake() -> None:
    assert probes.COUNTER_TAG.startswith("sbx-")
    assert Env().now() > 0


def test_real_http_get_sends_the_endpoint_headers(monkeypatch: pytest.MonkeyPatch) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text=request.headers["x-token"])

    client = httpx.Client(transport=httpx.MockTransport(handler))
    monkeypatch.setattr(httpx, "get", client.get)
    assert http_get(Endpoint("http://sandbox/", {"x-token": "t"})) == "t"
