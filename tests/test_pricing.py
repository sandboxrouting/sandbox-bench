from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from sandbox_bench import pricing

RATE = "{usd_per_hour: 0.1, source: 'https://x.example/p', checked: 2026-11-25}"


def write(tmp_path: Path, running: str = RATE, paused: str = RATE, size: str = "2, 4") -> Path:
    vcpu, mem = size.split(", ")
    path = tmp_path / "pricing.yaml"
    path.write_text(
        f"size: {{vcpu: {vcpu}, memory_gib: {mem}}}\n"
        f"providers:\n  p:\n    running: {running}\n    paused: {paused}\n",
        encoding="utf-8",
    )
    return path


def test_shipped_price_list_is_valid() -> None:
    prices = pricing.load().providers
    assert prices["daytona"].running.usd_per_hour == pytest.approx(2 * 0.0504 + 4 * 0.0162)
    assert prices["freestyle"].running.usd_per_hour == pytest.approx(2 * 0.04032 + 4 * 0.0129)
    for price in prices.values():
        paused = price.paused
        assert paused.usd_per_hour is not None or paused.note or paused.todo


def test_minimal_file_loads(tmp_path: Path) -> None:
    price = pricing.load(write(tmp_path)).providers["p"]
    assert price.running.checked.isoformat() == "2026-11-25"
    assert price.notes == []


@pytest.mark.parametrize(
    ("running", "paused", "size", "error"),
    [
        (RATE.replace("https", "http"), RATE, "2, 4", "https URL"),
        (RATE.replace("0.1", "-0.1"), RATE, "2, 4", "greater than or equal to 0"),
        (RATE.replace("2026-11-25", "25/11/2026"), RATE, "2, 4", "date"),
        (RATE, RATE.replace("0.1", "null"), "2, 4", "needs a `note` or a `todo`"),
        (RATE, RATE, "2, 8", "standard size"),
        (RATE.replace("}", ", fee: 1}"), RATE, "2, 4", "Extra inputs"),
    ],
)
def test_bad_files_are_rejected(
    tmp_path: Path, running: str, paused: str, size: str, error: str
) -> None:
    with pytest.raises(ValidationError, match=error):
        pricing.load(write(tmp_path, running, paused, size))


def test_null_price_with_todo_is_allowed(tmp_path: Path) -> None:
    paused = RATE.replace("0.1", "null").replace("}", ", todo: ask them}")
    assert pricing.load(write(tmp_path, paused=paused)).providers["p"].paused.todo == "ask them"
