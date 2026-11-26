"""The result schema: what one run writes, and what the results repo stores.

One ``RunRecord`` per run, as JSON. Everything published (tables, ``results.json``) is
derived from these records, so they hold raw observations only: verdicts with their evidence,
and client-side timings in seconds. No aggregates.

``SCHEMA_VERSION`` changes when a field changes meaning or is removed; adding an optional
field doesn't bump it.
"""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Final, Literal

from pydantic import AfterValidator, BaseModel, ConfigDict, Field

from sandbox_bench.adapter import Access, StartMode
from sandbox_bench.benchmark import PROBES

SCHEMA_VERSION: Final = 1

Outcome = Literal["pass", "fail", "excluded"]
"""``pass``/``fail`` are the verifier's verdict. ``excluded`` means the attempt hit one of
*our* errors (METHODOLOGY §5) and doesn't count either way."""

JsonScalar = str | int | float | bool | None
Evidence = dict[str, JsonScalar | list[JsonScalar]]


def _utc(value: datetime) -> datetime:
    if value.utcoffset() is None:
        msg = "timestamps must be timezone-aware"
        raise ValueError(msg)
    return value


UtcDatetime = Annotated[datetime, AfterValidator(_utc)]


def _known_probe(value: str) -> str:
    if value not in PROBES:
        msg = f"unknown probe {value!r}"
        raise ValueError(msg)
    return value


ProbeId = Annotated[str, AfterValidator(_known_probe)]


class _Model(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class SizeRecord(_Model):
    vcpu: float = Field(gt=0)
    memory_gib: float = Field(gt=0)


class Verdict(_Model):
    outcome: Outcome
    evidence: Evidence = Field(default_factory=dict)
    """What the verifier saw, e.g. expected and actual hashes, PIDs, counter reads."""
    error: str | None = None
    """For a failure or exclusion: the error, as ``Type: message``."""


class Attempt(_Model):
    provider: str
    action: str
    """The action that produced these verdicts, e.g. ``pause``."""
    index: int = Field(ge=0)
    """Attempt number within the run, per provider and action."""
    started_at: UtcDatetime
    finished_at: UtcDatetime
    verdicts: dict[ProbeId, Verdict]
    timings: dict[str, float] = Field(default_factory=dict)
    """Metric name -> seconds, client-side wall clock. Only for operations that succeeded."""
    default_create: bool = True
    """``False`` when the sandbox wasn't a default create (e.g. egress denied); such
    attempts never feed Start."""
    start_evidence: Evidence = Field(default_factory=dict)
    """``/proc/uptime`` and boot id at the first exec, as evidence for the start mode."""


class ProviderInfo(_Model):
    name: str
    product: str
    owner: str
    access: Access
    plan: str
    region: str
    start_mode: StartMode
    size: SizeRecord
    sdk: str
    offers: dict[ProbeId, str]
    mechanisms: dict[str, str] = Field(default_factory=dict)


class Runner(_Model):
    region: str
    """Where the runner machine is, e.g. ``us-east``."""
    host: str | None = None
    """Free-form machine description; never a hostname that identifies a person."""


class RunRecord(_Model):
    schema_version: Literal[1] = SCHEMA_VERSION
    benchmark: str
    run_id: str = Field(pattern=r"^[a-z0-9]+(-[a-z0-9]+)*$")
    harness_version: str
    git_sha: str | None = None
    runner: Runner
    started_at: UtcDatetime
    finished_at: UtcDatetime
    providers: list[ProviderInfo]
    attempts: list[Attempt]
    api_rtt: dict[str, list[float]] = Field(default_factory=dict)
    """Provider name -> API round-trip samples in seconds. Context only, never ranked."""
    log: list[str] = Field(default_factory=list)
    """Excluded errors and cleanup notes, one line each."""
