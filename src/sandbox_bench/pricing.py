"""List prices from ``pricing/pricing.yaml`` (METHODOLOGY §6), validated on load.

Each rate carries the page it comes from and the date it was checked there. A missing price
is ``None`` with a reason, never a guess.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Annotated, Self

import yaml
from pydantic import AfterValidator, BaseModel, ConfigDict, Field, model_validator

from sandbox_bench.adapter import STANDARD_SIZE

DEFAULT_PATH = Path(__file__).resolve().parents[2] / "pricing" / "pricing.yaml"


def _https(value: str) -> str:
    if not value.startswith("https://"):
        msg = f"source must be an https URL, got {value!r}"
        raise ValueError(msg)
    return value


class _Model(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class Rate(_Model):
    usd_per_hour: float | None = Field(ge=0)
    basis: str = ""
    """How the hourly figure is built from the listed unit rates."""
    source: Annotated[str, AfterValidator(_https)]
    checked: date
    note: str | None = None
    """Why there is no price, when the feature isn't offered."""
    todo: str | None = None
    """What still needs checking, when the feature is offered but no list price was found."""

    @model_validator(mode="after")
    def _explain_missing(self) -> Self:
        if self.usd_per_hour is None and not (self.note or self.todo):
            msg = "a null usd_per_hour needs a `note` or a `todo` saying why"
            raise ValueError(msg)
        return self


class ProviderPrice(_Model):
    running: Rate
    paused: Rate
    notes: list[str] = Field(default_factory=list)
    """Per-creation fees, minimums, free allowances, plan fees."""


class Size(_Model):
    vcpu: float
    memory_gib: float


class PriceList(_Model):
    size: Size
    providers: dict[str, ProviderPrice]

    @model_validator(mode="after")
    def _standard_size(self) -> Self:
        if (self.size.vcpu, self.size.memory_gib) != (STANDARD_SIZE.vcpu, STANDARD_SIZE.memory_gib):
            msg = f"prices must be for the standard size {STANDARD_SIZE}"
            raise ValueError(msg)
        return self


def load(path: Path = DEFAULT_PATH) -> PriceList:
    """Read and validate a price list. Raises ``pydantic.ValidationError`` on a bad file."""
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    return PriceList.model_validate(data)
