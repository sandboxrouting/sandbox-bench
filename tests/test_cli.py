"""The ``sbx`` command line, against the fake provider."""

from __future__ import annotations

import re
from collections.abc import Mapping
from pathlib import Path
from typing import Any, ClassVar

import pytest

from sandbox_bench import providers
from sandbox_bench.adapter import Adapter
from sandbox_bench.cli import main
from sandbox_bench.providers.fake import Fake
from sandbox_bench.schema import RunRecord


def squeeze(text: str) -> str:
    """Collapse table padding so assertions don't depend on column widths."""
    return re.sub(r" {2,}", " ", text)


def records(out: Path) -> list[RunRecord]:
    return [RunRecord.model_validate_json(p.read_text()) for p in sorted(out.rglob("*.json"))]


def use(monkeypatch: pytest.MonkeyPatch, **classes: type[Adapter[Any, Any]]) -> None:
    """Make ``sbx`` see extra provider classes by name."""
    real = providers.adapter_class
    monkeypatch.setattr(providers, "adapter_class", lambda n: classes.get(n) or real(n))


def test_providers(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["providers"]) == 0
    assert "fake\tsimulated\t11 offered probes" in capsys.readouterr().out


def test_run_writes_a_dated_record(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SBX_RUNNER_REGION", "test-region")
    assert main(["run", "--providers", "fake", "--attempts", "1", "--out", str(tmp_path)]) == 0
    (record,) = records(tmp_path)
    assert record.runner.region == "test-region"
    assert len(record.attempts) == 5
    assert (tmp_path / f"{record.started_at:%Y/%m/%d}" / f"{record.run_id}.json").exists()


def test_run_leaves_out_a_provider_that_cant_start(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    class NoKey(Fake):
        name = "nokey"

        def __init__(self) -> None:
            raise KeyError("NOKEY_API_KEY")

    use(monkeypatch, nokey=NoKey)
    argv = ["run", "--providers", "nokey,fake", "--attempts", "1", "--out", str(tmp_path)]
    assert main(argv) == 2
    (record,) = records(tmp_path)
    assert [p.name for p in record.providers] == ["fake"]
    assert record.log[0].startswith("nokey: not run: nokey: can't start the adapter: KeyError")
    assert "can't start" in capsys.readouterr().err
    assert main(["run", "--providers", "nokey", "--out", str(tmp_path)]) == 2


def test_check_prints_the_table(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    closed: list[bool] = []

    class Closing(Fake):
        def close(self) -> None:
            closed.append(True)

    use(monkeypatch, fake=Closing)
    argv = ["check", "fake", "--probe", "pause-keeps-memory", "--out", str(tmp_path)]
    assert main(argv) == 0
    out = capsys.readouterr().out
    assert "| pause-keeps-memory | 1/1 | pass | Start " in squeeze(out)
    # Timings sit on the probe that ran, never on a "not run" row.
    assert "| create-exec | - | not run | |" in squeeze(out)
    assert "| pause-keeps-files | - | not run | |" in squeeze(out)
    assert closed == [True]


def test_check_exits_1_when_a_probe_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    class Broken(Fake):
        def __init__(self) -> None:
            super().__init__(broken={"internet"})

    use(monkeypatch, fake=Broken)
    assert main(["check", "fake", "--probe", "internet", "--out", str(tmp_path)]) == 1
    assert "| internet | 0/1 |" in squeeze(capsys.readouterr().out)


def test_report(tmp_path: Path) -> None:
    runs, board = tmp_path / "runs", tmp_path / "board"
    assert main(["run", "--providers", "fake", "--attempts", "1", "--out", str(runs)]) == 0
    assert main(["report", str(runs), "--out", str(board)]) == 0
    assert (board / "leaderboard.md").exists()
    assert (board / "results.json").exists()


@pytest.mark.parametrize("content", [None, "{not json"])
def test_report_errors_are_clean(
    tmp_path: Path, content: str | None, capsys: pytest.CaptureFixture[str]
) -> None:
    if content is not None:
        (tmp_path / "bad.json").write_text(content)
    assert main(["report", str(tmp_path), "--out", str(tmp_path / "board")]) == 2
    assert capsys.readouterr().err.startswith(f"sbx: can't report on {tmp_path}")


def test_reap(capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch) -> None:
    assert main(["reap", "fake"]) == 0
    assert "deleted 0 resources named sbx-*" in capsys.readouterr().out

    class NoReap(Fake):
        reap = Adapter.reap

    use(monkeypatch, fake=NoReap)
    assert main(["reap", "fake"]) == 2


def test_validate(capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch) -> None:
    assert main(["validate", "fake"]) == 0

    class Invalid(Fake):
        offers: ClassVar[Mapping[str, str]] = {"teleport": "http://x"}

    use(monkeypatch, fake=Invalid)
    assert main(["validate", "fake"]) == 1
    assert "offers unknown probe 'teleport'" in capsys.readouterr().out
    assert main(["check", "fake"]) == 2
    assert main(["validate", "nope"]) == 2


def test_unknown_provider(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["check", "nope"]) == 2
    assert "unknown provider 'nope'" in capsys.readouterr().err
