"""The ``sbx`` command line.

Credentials come from environment variables only, read by each adapter; nothing here prints
them. Exit codes: 0 done, 1 something failed (a probe in ``sbx check``, a problem in
``sbx validate``), 2 a usage or configuration error.
"""

from __future__ import annotations

import argparse
import os
import sys
from collections.abc import Sequence
from pathlib import Path

from pydantic import ValidationError

from sandbox_bench import __version__, providers, report
from sandbox_bench.adapter import RESOURCE_PREFIX
from sandbox_bench.benchmark import ATTEMPTS_PER_RUN, PROBES
from sandbox_bench.providers import AnyAdapter
from sandbox_bench.runner import Run, git_sha, write_record
from sandbox_bench.schema import RunRecord


class UsageError(Exception):
    """A configuration problem: reported in one line, exit code 2."""


def _load(name: str) -> AnyAdapter:
    try:
        cls = providers.adapter_class(name)
    except LookupError as exc:
        raise UsageError(str(exc)) from exc
    problems = providers.validate(cls)
    if problems:
        raise UsageError(f"{name}: invalid adapter: {'; '.join(problems)}")
    try:
        return cls()
    except Exception as exc:  # missing credentials, SDK import errors, ...
        raise UsageError(f"{name}: can't start the adapter: {type(exc).__name__}: {exc}") from exc


def _run(
    args: argparse.Namespace,
    adapters: list[AnyAdapter],
    only: Sequence[str] | None = None,
    log: Sequence[str] = (),
) -> RunRecord:
    run = Run(
        adapters,
        attempts=args.attempts,
        seed=args.seed,
        only=frozenset(only) if only else None,
        region=os.environ.get("SBX_RUNNER_REGION", "us-east"),
        git_sha=git_sha(),
        log=list(log),
    )
    try:
        record = run.run()
    finally:
        for adapter in adapters:
            close = getattr(adapter, "close", None)
            if callable(close):
                close()
    print(f"wrote {write_record(record, args.out)}", file=sys.stderr)
    return record


def _cmd_providers(_: argparse.Namespace) -> int:
    for name in providers.available():
        cls = providers.adapter_class(name)
        print(f"{name}\t{cls.product}\t{len(cls.offers)} offered probes")
    return 0


def _cmd_run(args: argparse.Namespace) -> int:
    """Exit 0 when the run completed, however the providers did. A provider that can't start
    (e.g. a missing key) is left out and logged, and the exit code is 2."""
    adapters, problems = [], []
    for name in [n for n in args.providers.split(",") if n]:
        try:
            adapters.append(_load(name))
        except UsageError as exc:
            print(f"sbx: {exc}", file=sys.stderr)
            problems.append(f"{name}: not run: {exc}")
    if not adapters:
        raise UsageError("no provider could start")
    _run(args, adapters, log=problems)
    return 2 if problems else 0


def _cmd_check(args: argparse.Namespace) -> int:
    record = _run(args, [_load(args.provider)], args.probe)
    print(report.check_table(record))
    outcomes = [v.outcome for a in record.attempts for v in a.verdicts.values()]
    return 0 if outcomes and all(o == "pass" for o in outcomes) else 1


def _cmd_report(args: argparse.Namespace) -> int:
    paths = sorted(args.results.rglob("*.json"))
    try:
        records = [RunRecord.model_validate_json(p.read_text(encoding="utf-8")) for p in paths]
        report.write_report(records, args.out)
    except (ValidationError, ValueError) as exc:
        raise UsageError(f"can't report on {args.results}: {exc}") from exc
    print(f"reported {len(records)} runs into {args.out}", file=sys.stderr)
    return 0


def _cmd_reap(args: argparse.Namespace) -> int:
    adapter = _load(args.provider)
    if not adapter.implements("reap"):
        raise UsageError(f"{args.provider} has no reap()")
    print(f"deleted {adapter.reap(RESOURCE_PREFIX)} resources named {RESOURCE_PREFIX}*")
    return 0


def _cmd_validate(args: argparse.Namespace) -> int:
    problems = providers.validate(providers.adapter_class(args.provider))
    for problem in problems:
        print(problem)
    print(f"{args.provider}: {len(problems) or 'no'} problems", file=sys.stderr)
    return 1 if problems else 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="sbx", description="Benchmark AI-agent sandboxes.")
    parser.add_argument("--version", action="version", version=f"sbx {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("providers", help="list provider adapters").set_defaults(func=_cmd_providers)

    def runs(name: str, help_: str, attempts: int) -> argparse.ArgumentParser:
        p = sub.add_parser(name, help=help_)
        p.add_argument("--attempts", type=int, default=attempts, help="attempts per action")
        p.add_argument("--seed", type=int, help="seed for the shuffled order")
        p.add_argument("--out", type=Path, default=Path("results"), help="where to write runs")
        return p

    run = runs("run", "run every offered probe on some providers", ATTEMPTS_PER_RUN)
    run.add_argument("--providers", required=True, help="comma-separated provider names")
    run.set_defaults(func=_cmd_run)
    check = runs("check", "run probes on one provider and print a table", 1)
    check.add_argument("provider")
    check.add_argument("--probe", action="append", choices=PROBES, help="repeatable")
    check.set_defaults(func=_cmd_check)
    rep = sub.add_parser("report", help="score run records and write the tables")
    rep.add_argument("results", type=Path, help="directory of run records, searched recursively")
    rep.add_argument("--out", type=Path, required=True)
    rep.set_defaults(func=_cmd_report)
    for name, func in (("reap", _cmd_reap), ("validate", _cmd_validate)):
        p = sub.add_parser(name, help=f"{name} one provider")
        p.add_argument("provider")
        p.set_defaults(func=func)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        result: int = args.func(args)
    except (UsageError, LookupError) as exc:
        print(f"sbx: {exc}", file=sys.stderr)
        return 2
    return result
