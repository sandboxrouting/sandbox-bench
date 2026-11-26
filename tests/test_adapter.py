from __future__ import annotations

import pytest

from sandbox_bench import providers
from sandbox_bench.adapter import Adapter, ExecResult, NotOffered, Size, Spec
from sandbox_bench.benchmark import PROBES, REQUIRES, check_offers


def test_spec_requires_prefix() -> None:
    with pytest.raises(ValueError, match="must start with"):
        Spec(name="mine")
    assert Spec(name="sbx-run-1").size == Size(2, 4)


def test_size_str() -> None:
    assert str(Size(2, 4)) == "2 vCPU / 4 GiB"
    assert str(Size(0.5, 1.5)) == "0.5 vCPU / 1.5 GiB"


def test_exec_result_ok() -> None:
    assert ExecResult(0, "").ok
    assert not ExecResult(1, "").ok


def test_requires_covers_every_probe() -> None:
    assert set(REQUIRES) == set(PROBES)


def test_check_offers() -> None:
    assert check_offers({}, {}) == []
    problems = check_offers(
        {"nope": "https://x", "pause-keeps-memory": "http://x"}, {"pause": True}
    )
    assert problems == [
        "offers unknown probe 'nope'",
        "pause-keeps-memory: docs link must be an https URL, got 'http://x'",
        "pause-keeps-memory: offered but resume() isn't implemented",
    ]


def test_optional_operations_raise_not_offered() -> None:
    fake = providers.adapter_class("fake")()
    sb = fake.create(Spec(name="sbx-t"))
    with pytest.raises(NotOffered):
        Adapter.pause(fake, sb)
    assert not type(fake).implements("nonexistent")


def test_wait_until() -> None:
    calls = iter([False, False, True])
    Adapter.wait_until(lambda: next(calls), timeout_s=1, interval_s=0)
    with pytest.raises(TimeoutError, match="waiting for thing"):
        Adapter.wait_until(lambda: False, timeout_s=0, interval_s=0, what="thing")


@pytest.mark.parametrize("name", providers.available())
def test_every_provider_is_valid(name: str) -> None:
    assert providers.validate(providers.adapter_class(name)) == []


def test_unknown_provider() -> None:
    with pytest.raises(LookupError, match="unknown provider"):
        providers.adapter_class("does-not-exist")
