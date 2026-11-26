"""Render scored boards: ``leaderboard.md`` and ``results.json`` for a report, and the compact
table ``sbx check`` prints (METHODOLOGY §5, §6)."""

from __future__ import annotations

import json
import statistics
from collections.abc import Mapping, Sequence
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Any

from sandbox_bench import boards, pricing
from sandbox_bench.adapter import STANDARD_SIZE
from sandbox_bench.benchmark import ALWAYS_OFFERED, PASS_THRESHOLD, PROBES, WINDOW
from sandbox_bench.boards import COLUMNS, Board, Column, Failure, ProviderBoard, fmt_s
from sandbox_bench.schema import SCHEMA_VERSION, Attempt, ProviderInfo, RunRecord

RESULTS_FORMAT = 1
"""Version of the ``results.json`` layout; bumps when a key changes meaning or goes away."""

Prices = Mapping[str, pricing.ProviderPrice]
PAUSE_PROBES = ("pause-keeps-files", "pause-keeps-memory")


def write_report(
    records: Sequence[RunRecord], out_dir: Path, *, pricing_path: Path = pricing.DEFAULT_PATH
) -> None:
    """Score ``records`` and write ``leaderboard.md`` and ``results.json`` into ``out_dir``."""
    board = boards.build(records)
    prices = pricing.load(pricing_path).providers
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "leaderboard.md").write_text(render_markdown(board, prices), encoding="utf-8")
    data = results(board, prices)
    text = json.dumps(data, indent=2, sort_keys=True, ensure_ascii=False, default=_json)
    (out_dir / "results.json").write_text(text + "\n", encoding="utf-8")


# ---- formatting helpers ------------------------------------------------------------------------
def _name(info: ProviderInfo) -> str:
    return f"{info.name} ({info.product})"


def _size(info: ProviderInfo) -> str:
    return f"{info.size.vcpu:g} vCPU / {info.size.memory_gib:g} GiB"


def _day(when: datetime | None) -> str:
    return when.date().isoformat() if when else "-"


def _span(first: datetime | None, last: datetime | None) -> str:
    a, b = _day(first), _day(last)
    return a if a == b else f"{a} to {b}"


def _usd(value: float | None) -> str:
    if value is None:
        return "?"
    return f"{value:.2f}" if value >= 0.01 or value == 0 else f"{value:.2g}"


def _price(p: ProviderBoard, prices: Prices) -> str:
    price = prices.get(p.info.name)
    if price is None:
        return "?"
    pause_offered = any(probe in p.info.offers for probe in PAUSE_PROBES)
    paused = _usd(price.paused.usd_per_hour) if pause_offered else "n/a"
    return f"{_usd(price.running.usd_per_hour)} / {paused}"


def _cell(p: ProviderBoard, col: Column) -> str:
    stat = p.shown(col)
    if stat is None:
        return p.blank(col)
    if col.metric == "start":
        return f"{fmt_s(stat.p50)} ({boards.START_LABEL[p.info.start_mode]})"
    return fmt_s(stat.p50)


def _score(p: ProviderBoard) -> str:
    text = boards.fmt_score(p.passed)
    if failing := p.with_status("failing"):
        text += f", failing: {', '.join(failing)}"
    if pending := p.with_status("pending"):
        text += f", {len(pending)} pending"
    return text


def _reproduce(provider: str, probe: str) -> str:
    return f"sbx check {provider} --probe {probe}"


def _failure_line(provider: str, probe: str, counted: str, f: Failure | None) -> str:
    line = f"- **{provider}** `{probe}` verified {counted}."
    if f:
        evidence = json.dumps(f.evidence, sort_keys=True).replace("`", "'")
        line += (
            f" Last failure: run `{f.run_id}`, {f.action} attempt {f.index}"
            f" ({_day(f.started_at)}): {f.error or 'no error message'}. Evidence: `{evidence}`."
        )
    return line + f" Reproduce: `{_reproduce(provider, probe)}`"


def _table(header: Sequence[str], rows: Sequence[Sequence[str]]) -> list[str]:
    """A Markdown table with padded columns, so it also reads well in a terminal."""
    widths = [max(len(c) for c in col) for col in zip(header, *rows, strict=True)]

    def line(cells: Sequence[str]) -> str:
        return "| " + " | ".join(c.ljust(w) for c, w in zip(cells, widths, strict=True)) + " |"

    return [line(header), "|" + "|".join("-" * (w + 2) for w in widths) + "|"] + [
        line(r) for r in rows
    ]


# ---- leaderboard.md ----------------------------------------------------------------------------
def render_markdown(board: Board, prices: Prices) -> str:
    size = f"every sandbox {STANDARD_SIZE}"
    if not all(p.standard_size for p in board.providers):
        size = f"{STANDARD_SIZE} requested, actual sizes in the tables below"
    out = [
        f"# sandbox-bench leaderboard ({board.version})",
        "",
        f"*As of {_day(board.last)} · attempts from {_span(board.first, board.last)} · "
        f"runner in {', '.join(board.runner_regions)} · {size}*",
        "",
    ]
    main = [c for c in COLUMNS if c.main]
    header = ["#", "Provider", "Probes passed", "Keeps memory on", *(c.title for c in main)]
    rows = [
        [
            str(board.rank(p) or "-"),
            _name(p.info),
            _score(p),
            ", ".join(p.keeps_memory()) or "none",
            *(_cell(p, c) for c in main),
            _price(p, prices),
        ]
        for p in board.providers
    ]
    out += _table([*header, "$/h running / paused"], rows)
    out += [
        "",
        f"A probe passes at {PASS_THRESHOLD} of its last {WINDOW} attempts. Times are medians of"
        f" the last {WINDOW}, shown only when the probe behind the column passes."
        f' "-" = not ranked yet (a probe has fewer than {WINDOW} attempts).'
        ' "?" = no list price found yet, see `pricing/pricing.yaml`.',
    ]
    for col in COLUMNS:
        out += ["", *_metric_table(board, col)]
    out += ["", "## Providers", ""]
    for p in board.providers:
        out.append(f"- **{_name(p.info)}**: {p.facts()}")
        if price := prices.get(p.info.name):
            run = price.running
            basis = f" ({run.basis})" if run.basis else ""
            out.append(
                f"  Price ($/h running / paused): {_price(p, prices)}{basis}, {run.source}"
                f" (checked {run.checked}). {' '.join(price.notes)}".rstrip()
            )
    failing = [
        _failure_line(p.info.name, probe, f"{r.passed}/{r.counted}", r.last_failure)
        for p in board.providers
        for probe, r in p.probes.items()
        if r.status == "failing"
    ]
    if failing:
        out += ["", "## Failing probes", "", *failing]
    return "\n".join(out) + "\n"


def _metric_table(board: Board, col: Column) -> list[str]:
    ranked_at = "2 vCPU / 4 GiB only" if col.state else "any size"
    out = [
        f"### {col.title}",
        "",
        f"Shown when `{col.gate}` passes. Ranked with {WINDOW} samples, at {ranked_at}.",
        "",
    ]
    rows = []
    for rank, p, s in board.column(col):
        gate = p.probes[col.gate]
        rtt = fmt_s(p.api_rtt) if p.api_rtt is not None else "-"
        info = p.info
        rows.append(
            [
                str(rank or "-"),
                _name(info),
                fmt_s(s.p50),
                fmt_s(s.p90),
                str(s.n),
                f"{gate.passed}/{gate.counted}",
                _span(s.first, s.last),
                info.plan,
                _size(info),
                info.region,
                rtt,
            ]
        )
    header = ["#", "Provider", "p50", "p90", "n", "Success", "Window", "Plan", "Size", "Region"]
    out += _table([*header, "API RTT"], rows) if rows else ["No provider passes it yet."]
    hidden = [f"{p.info.name} ({p.blank(col)})" for p in board.providers if p.shown(col) is None]
    return out + (["", f"Not shown: {', '.join(hidden)}."] if hidden else [])


# ---- results.json ------------------------------------------------------------------------------
def _json(value: object) -> str:
    if isinstance(value, datetime):
        return value.isoformat()
    raise TypeError(type(value).__name__)


def results(board: Board, prices: Prices) -> dict[str, Any]:
    """The machine-readable aggregates (datetimes left for ``json.dumps(default=...)``).
    Keys are stable within ``RESULTS_FORMAT``."""
    providers = []
    for p in board.providers:
        info, price = p.info, prices.get(p.info.name)
        columns = {
            c.metric: {
                **asdict(s),
                "title": c.title,
                "gate": c.gate,
                "shown": p.shown(c) is not None,
                "ranked": p.ranked_in(c),
                "rank": next((r for r, q, _ in board.column(c) if q is p), None),
            }
            for c in COLUMNS
            if (s := p.metrics.get(c.metric))
        }
        providers.append(
            {
                "name": info.name,
                "product": info.product,
                "rank": board.rank(p),
                "score": {
                    "passed": p.passed,
                    "total": len(PROBES),
                    "text": boards.fmt_score(p.passed),
                },
                "plan": info.plan,
                "region": info.region,
                "start_mode": info.start_mode,
                "size": {"vcpu": info.size.vcpu, "memory_gib": info.size.memory_gib},
                "standard_size": p.standard_size,
                "mechanisms": dict(info.mechanisms),
                "keeps_memory_on": p.keeps_memory(),
                "facts": p.facts(),
                "api_rtt_p50": p.api_rtt,
                "probes": {
                    probe: {
                        "status": r.status,
                        "passed": r.passed,
                        "counted": r.counted,
                        "offers": info.offers.get(probe),
                        "last_failure": asdict(r.last_failure) if r.last_failure else None,
                        "reproduce": _reproduce(info.name, probe),
                    }
                    for probe, r in p.probes.items()
                },
                "metrics": columns,
                "price": price.model_dump(mode="json") if price else None,
            }
        )
    return {
        "benchmark": board.version,
        "schema_version": SCHEMA_VERSION,
        "results_format": RESULTS_FORMAT,
        "window": WINDOW,
        "pass_threshold": PASS_THRESHOLD,
        "probes": list(PROBES),
        "run_ids": list(board.run_ids),
        "runner_regions": list(board.runner_regions),
        "first": board.first,
        "last": board.last,
        "providers": providers,
    }


# ---- sbx check ---------------------------------------------------------------------------------
def _check_timings(own: list[Attempt]) -> dict[str, list[str]]:
    """Median timings by the probe row they're shown on: the column's gate probe, or, when the
    gate didn't run (``--probe``), the first probe that ran in the attempts that were timed."""
    by_row: dict[str, list[str]] = {}
    for c in COLUMNS:
        if not (pts := boards.samples(own, c)):
            continue
        ran = [p for p in PROBES if any(p in a.verdicts for a in own if c.metric in a.timings)]
        row = c.gate if c.gate in ran or not ran else ran[0]
        median = statistics.median(v for _, v in pts)
        by_row.setdefault(row, []).append(f"{c.title} {fmt_s(median)}")
    return by_row


def check_table(record: RunRecord) -> str:
    """A compact table for one ``sbx check`` run: raw counts, no 9-of-10 window."""
    out: list[str] = []
    excluded = 0
    for info in record.providers:
        own = [a for a in record.attempts if a.provider == info.name]
        rows, failures = [], []
        timings = _check_timings(own)
        for probe in PROBES:
            verdicts = [(a, a.verdicts[probe]) for a in own if probe in a.verdicts]
            excluded += sum(v.outcome == "excluded" for _, v in verdicts)
            counted = [(a, v) for a, v in verdicts if v.outcome != "excluded"]
            passed = sum(v.outcome == "pass" for _, v in counted)
            if counted:
                outcome = "pass" if passed == len(counted) else "fail"
            else:
                offered = probe in info.offers or probe in ALWAYS_OFFERED
                outcome = "not run" if offered else "n/a"
            verified = f"{passed}/{len(counted)}" if counted else "-"
            rows.append([probe, verified, outcome, ", ".join(timings.get(probe, []))])
            if last := [(a, v) for a, v in counted if v.outcome == "fail"][-1:]:
                a, v = last[0]
                f = Failure(record.run_id, a.action, a.index, a.started_at, v.error, v.evidence)
                failures.append(_failure_line(info.name, probe, f"{passed}/{len(counted)}", f))
        out += [f"**{_name(info)}**, run `{record.run_id}`", ""]
        out += _table(["Probe", "Verified", "Outcome", "Median"], rows)
        out += ["", *failures, ""] if failures else [""]
    note = f" {excluded} excluded (our errors, see the run log)." if excluded else ""
    out.append(
        f"Raw counts from this run. The leaderboard counts a probe as passing at"
        f" {PASS_THRESHOLD} of its last {WINDOW} attempts.{note}"
    )
    return "\n".join(out) + "\n"
