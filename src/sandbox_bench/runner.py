"""One benchmark run: every offered action on every provider, shuffled, one operation at a time.

Order of a run (METHODOLOGY §1, §7): reap leftovers, one uncounted warm-up create per
provider, then the shuffled attempts and API pings, then reap again. Writes one ``RunRecord``.
"""

from __future__ import annotations

import random
import secrets
import subprocess
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

from sandbox_bench import __version__
from sandbox_bench.adapter import RESOURCE_PREFIX, AccountError
from sandbox_bench.benchmark import ALWAYS_OFFERED, ATTEMPTS_PER_RUN, VERSION
from sandbox_bench.harness import Env, Pacer, ProviderError, with_deadline
from sandbox_bench.probes import Action, Context, actions
from sandbox_bench.providers import AnyAdapter
from sandbox_bench.schema import Attempt, ProviderInfo, Runner, RunRecord, SizeRecord, Verdict

REAP_TIMEOUT_S = 600.0


def new_run_id(now: datetime) -> str:
    """Sortable, lowercase and short, since it goes into every resource name."""
    return f"{now:%Y%m%d-%H%M%S}-{secrets.token_hex(2)}"


def wanted(adapter: AnyAdapter, action: Action, only: Iterable[str] | None = None) -> list[str]:
    """The action's probes this provider is tested on: what it offers, plus ALWAYS_OFFERED."""
    offered = set(adapter.offers) | ALWAYS_OFFERED
    keep = offered if only is None else offered & set(only)
    return [p for p in action.verdicts if p in keep]


def provider_info(adapter: AnyAdapter) -> ProviderInfo:
    fields = ("name", "product", "owner", "access", "plan", "region", "start_mode", "sdk")
    return ProviderInfo(
        **{f: getattr(adapter, f) for f in fields},
        size=SizeRecord(vcpu=adapter.size.vcpu, memory_gib=adapter.size.memory_gib),
        offers=dict(adapter.offers),
        mechanisms=dict(adapter.mechanisms),
    )


def _utcnow() -> datetime:
    return datetime.now(UTC)


@dataclass
class Run:
    """``strict`` re-raises harness bugs (tests). Otherwise they are excluded and logged, as
    METHODOLOGY §5 asks, so one bug doesn't throw away a whole day's run."""

    adapters: Sequence[AnyAdapter]
    attempts: int = ATTEMPTS_PER_RUN
    seed: int | None = None
    only: frozenset[str] | None = None
    env: Env = field(default_factory=Env)
    strict: bool = False
    region: str = "us-east"
    git_sha: str | None = None
    run_id: str = ""
    log: list[str] = field(default_factory=list)
    api_rtt: dict[str, list[float]] = field(default_factory=dict)
    _pacers: dict[str, Pacer] = field(default_factory=dict)

    def env_for(self, adapter: AnyAdapter) -> Env:
        """The fake provider brings a simulated clock and network (``simulated_env``)."""
        simulated = getattr(adapter, "simulated_env", None)
        return simulated if isinstance(simulated, Env) else self.env

    def harness(
        self,
        adapter: AnyAdapter,
        prefix: str,
        wanted: Sequence[str] = (),
        timings: Sequence[str] = ("start",),
    ) -> Context:
        env = self.env_for(adapter)
        pacer = self._pacers.setdefault(adapter.name, Pacer(adapter.pacing_s, env))
        name = f"{RESOURCE_PREFIX}{self.run_id}-{prefix}"
        return Context(adapter, prefix=name, wanted=wanted, timings=timings, env=env, pacer=pacer)

    def run(self) -> RunRecord:
        started = _utcnow()
        self.run_id = self.run_id or new_run_id(started)
        rng = random.Random(self.seed)  # noqa: S311 - a seedable shuffle, not crypto
        for adapter in self.adapters:
            self.reap(adapter, "before")
        for adapter in rng.sample(list(self.adapters), len(self.adapters)):
            self.warm_up(adapter)
        records: list[Attempt] = []
        for adapter, action, index in self.schedule(rng):
            if action is None:
                self.ping(adapter)
            else:
                records.append(self.attempt(adapter, action, index))
        for adapter in self.adapters:
            self.reap(adapter, "after")
        return RunRecord(
            benchmark=VERSION,
            run_id=self.run_id,
            harness_version=__version__,
            git_sha=self.git_sha,
            runner=Runner(region=self.region),
            started_at=started,
            finished_at=_utcnow(),
            providers=[provider_info(a) for a in self.adapters],
            attempts=records,
            api_rtt=self.api_rtt,
            log=self.log,
        )

    def schedule(self, rng: random.Random) -> list[tuple[AnyAdapter, Action | None, int]]:
        """Every attempt and API ping, shuffled across providers and actions."""
        items: list[tuple[AnyAdapter, Action | None, int]] = [
            (a, act, i)
            for a in self.adapters
            for act in actions()
            if wanted(a, act, self.only)
            for i in range(self.attempts)
        ]
        items += [
            (a, None, i)
            for a in self.adapters
            if a.implements("ping")
            for i in range(self.attempts)
        ]
        rng.shuffle(items)
        return items

    def attempt(self, adapter: AnyAdapter, action: Action, index: int) -> Attempt:
        probes = wanted(adapter, action, self.only)
        h = self.harness(adapter, f"{action.name}-{index}", probes, action.timings)
        started = _utcnow()
        try:
            checks = action.fn(h)
            verdicts = {
                p: Verdict(
                    outcome="pass" if checks[p].ok else "fail",
                    evidence=checks[p].evidence,
                    error=checks[p].error,
                )
                for p in probes
            }
        except ProviderError as exc:
            verdicts = {
                p: Verdict(outcome="fail", evidence={"op": exc.op}, error=str(exc)) for p in probes
            }
        except AccountError as exc:
            verdicts = self.exclude(adapter, action, index, probes, f"AccountError: {exc}")
        except Exception as exc:
            if self.strict:
                raise
            error = f"HarnessError: {type(exc).__name__}: {exc}"
            verdicts = self.exclude(adapter, action, index, probes, error)
        finally:
            h.cleanup()
            self.log.extend(h.log)
        return Attempt(
            provider=adapter.name,
            action=action.name,
            index=index,
            started_at=started,
            finished_at=_utcnow(),
            verdicts=verdicts,
            timings=h.timings,
            default_create=h.default_create,
            start_evidence=h.start_evidence,
        )

    def exclude(
        self, adapter: AnyAdapter, action: Action, index: int, probes: list[str], error: str
    ) -> dict[str, Verdict]:
        self.log.append(f"{adapter.name} {action.name}#{index}: excluded: {error}")
        return {p: Verdict(outcome="excluded", error=error) for p in probes}

    def warm_up(self, adapter: AnyAdapter) -> None:
        """One uncounted create per provider, so the first measured create isn't special."""
        h = self.harness(adapter, "warmup")
        try:
            h.create()
        except (ProviderError, AccountError) as exc:
            self.log.append(f"{adapter.name}: warm-up failed: {exc}")
        finally:
            h.cleanup()
            self.log.extend(h.log)

    def ping(self, adapter: AnyAdapter) -> None:
        h = self.harness(adapter, "ping", timings=["api_rtt"])
        try:
            h.timed("api_rtt", lambda: h.call("ping", adapter.ping))
        except (ProviderError, AccountError) as exc:
            self.log.append(f"{adapter.name}: ping failed: {exc}")
        else:
            self.api_rtt.setdefault(adapter.name, []).append(h.timings["api_rtt"])

    def reap(self, adapter: AnyAdapter, when: str) -> None:
        """Delete everything named with the ``sbx-`` prefix (METHODOLOGY §7)."""
        if not adapter.implements("reap"):
            self.log.append(f"{adapter.name}: no reaper; leftovers aren't cleaned up")
            return
        try:
            n = with_deadline(adapter.reap, [RESOURCE_PREFIX], REAP_TIMEOUT_S, "reap")
        except Exception as exc:  # noqa: BLE001 - a failed reap is logged and the run goes on
            self.log.append(f"{adapter.name}: reap {when} run failed: {type(exc).__name__}: {exc}")
        else:
            if n:
                self.log.append(f"{adapter.name}: reaped {n} leftover resources {when} the run")


def write_record(record: RunRecord, out_dir: Path) -> Path:
    """Write ``<out_dir>/YYYY/MM/DD/<run_id>.json``, the layout ``sbx report`` reads."""
    path = out_dir / f"{record.started_at:%Y/%m/%d}" / f"{record.run_id}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(record.model_dump_json(indent=2) + "\n", encoding="utf-8")
    return path


def git_sha() -> str | None:
    """The harness commit, when running from a git checkout."""
    try:
        out = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=Path(__file__).parent,
            capture_output=True,
            text=True,
            check=True,
            timeout=10,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    return out.stdout.strip() or None
