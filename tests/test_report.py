"""Rendered output: golden Markdown under ``tests/golden/`` and the ``results.json`` shape.

Regenerate the golden files after an intended change with ``SBX_UPDATE_GOLDEN=1 uv run pytest``
and review the diff.
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path

import pytest

from sandbox_bench import boards, report
from sandbox_bench.benchmark import PROBES, VERSION
from sandbox_bench.schema import RunRecord
from test_boards import attempts, info, record

GOLDEN = Path(__file__).parent / "golden"
PRICES = """\
size: {vcpu: 2, memory_gib: 4}
providers:
  alpha:
    running: {usd_per_hour: 0.1656, basis: 2 x 0.0504 + 4 x 0.0162,
              source: 'https://alpha.example/pricing', checked: 2026-11-25}
    paused: {usd_per_hour: null, note: not offered,
             source: 'https://alpha.example/pricing', checked: 2026-11-25}
    notes: [Billed per second.]
  beta:
    running: {usd_per_hour: 0.13, source: 'https://beta.example/pricing', checked: 2026-11-26}
    paused: {usd_per_hour: 0.004, source: 'https://beta.example/pricing', checked: 2026-11-26}
"""
ALPHA_OFFERS = [*PROBES[:5], "snapshot-keeps-files"]


def assert_golden(name: str, text: str) -> None:
    path = GOLDEN / name
    if os.environ.get("SBX_UPDATE_GOLDEN"):
        path.write_text(text, encoding="utf-8")
    assert text == path.read_text(encoding="utf-8")


@pytest.fixture
def prices(tmp_path: Path) -> Path:
    path = tmp_path / "pricing.yaml"
    path.write_text(PRICES, encoding="utf-8")
    return path


@pytest.fixture
def records() -> list[RunRecord]:
    alpha = attempts(
        "alpha",
        probes=ALPHA_OFFERS,
        timings={"start": 1.6, "exec": 0.04, "snapshot": 368.0, "restore": 1.8},
        fail={"egress-block": 4},
    )
    beta = attempts(
        "beta",
        timings={"start": 0.9, "resume": 0.3, "restore": 0.8, "fork": 1.1, "pause": 0.2},
    )
    gamma = attempts("gamma", 5, timings={"start": 0.4, "resume": 0.1})
    providers = [
        info("alpha", ALPHA_OFFERS),
        info("beta", start_mode="memory", mechanisms={"fork": "snapshot, then restore"}),
        info("gamma", size=(2, 8), start_mode="pool"),
    ]
    return [record(providers, alpha + beta + gamma, api_rtt={"beta": [0.05, 0.07]})]


def test_leaderboard_markdown(records: list[RunRecord], prices: Path, tmp_path: Path) -> None:
    report.write_report(records, tmp_path / "out", pricing_path=prices)
    assert_golden("leaderboard.md", (tmp_path / "out" / "leaderboard.md").read_text())


def test_results_json(records: list[RunRecord], prices: Path, tmp_path: Path) -> None:
    report.write_report(records, tmp_path, pricing_path=prices)
    data = json.loads((tmp_path / "results.json").read_text())
    assert (data["benchmark"], data["schema_version"], data["results_format"]) == (VERSION, 1, 1)
    assert [p["name"] for p in data["providers"]] == ["beta", "alpha", "gamma"]
    alpha = data["providers"][1]
    assert alpha["rank"] == 2
    assert alpha["score"] == {"passed": 5, "total": 11, "text": "45% (5 of 11)"}
    egress = alpha["probes"]["egress-block"]
    assert egress["status"] == "failing"
    assert egress["reproduce"] == "sbx check alpha --probe egress-block"
    assert egress["last_failure"]["evidence"] == {"expected": "abc", "actual": "xyz"}
    assert alpha["metrics"]["snapshot"]["p50"] == 368.0
    assert alpha["metrics"]["start"]["rank"] == 2
    assert alpha["price"]["paused"]["note"] == "not offered"
    gamma = data["providers"][2]
    assert gamma["rank"] is None
    assert gamma["metrics"]["resume"]["shown"] is False
    assert gamma["price"] is None


def test_check_table(records: list[RunRecord]) -> None:
    rec = records[0]
    five = attempts("alpha", 5, ALPHA_OFFERS[:4], timings={"start": 1.2}, fail={"egress-block": 1})
    excluded = attempts("alpha", 1, ["internet"], excluded=True, hour=30)
    one = rec.model_copy(update={"providers": rec.providers[:1], "attempts": five + excluded})
    assert_golden("check.md", report.check_table(one))


def test_report_refuses_mixed_versions(records: list[RunRecord], tmp_path: Path) -> None:
    old = records[0].model_copy(update={"benchmark": "v0.0", "run_id": "old"})
    with pytest.raises(ValueError, match="mix benchmark versions"):
        report.write_report([*records, old], tmp_path)
    assert not (tmp_path / "leaderboard.md").exists()


def test_empty_columns_and_unknown_paused_price(tmp_path: Path) -> None:
    offers = ["create-exec", "pause-keeps-files"]
    atts = attempts("beta", 10, offers, fail={"create-exec": 3, "pause-keeps-files": 3})
    prices = tmp_path / "pricing.yaml"
    prices.write_text(PRICES.replace("usd_per_hour: 0.004", "usd_per_hour: null, todo: ask"))
    report.write_report([record([info("beta", offers)], atts)], tmp_path, pricing_path=prices)
    text = (tmp_path / "leaderboard.md").read_text()
    assert "| 0.13 / ? |" in re.sub(r" {2,}", " ", text)
    assert text.count("No provider passes it yet.") == len(boards.COLUMNS)
    assert (
        "*As of 2026-11-20 · attempts from 2026-11-20 · runner in us-east · every sandbox 2" in text
    )
