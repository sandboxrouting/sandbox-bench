"""The provider adapter interface.

An adapter maps the harness's handful of operations onto one provider's public SDK or REST
API. It does no timing, retrying, pre-warming or caching: the harness owns all of that, so
every provider is measured the same way (CONTRIBUTING, "Adapter rules").

Required: ``create``, ``exec`` and ``destroy``. Everything else is optional and only needs to
exist when the provider offers the matching probe in ``offers``.

Handles are opaque to the harness. ``SB`` is whatever identifies a running sandbox for the
provider (an SDK object, an id string, ...), and ``SNAP`` the same for a snapshot.
"""

from __future__ import annotations

import time
from abc import ABC, abstractmethod
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from typing import ClassVar, Literal

StartMode = Literal["pool", "memory", "cold"]
"""How a default create is served: a pre-started pool, a memory-snapshot boot, or a cold boot."""

Access = Literal["sdk", "rest"]

RESOURCE_PREFIX = "sbx-"
"""Every resource the harness creates is named with this prefix; the reaper relies on it."""


class NotOffered(Exception):  # noqa: N818 - reads naturally at raise sites
    """Raised by an optional operation the provider doesn't implement."""


class AccountError(Exception):
    """A failure on *our* side: expired key, exhausted credits, an account or plan limit.

    Attempts that end in an ``AccountError`` are excluded from scores and listed in the run
    log (METHODOLOGY §5). Raise it only for those causes, never for a provider fault: any
    other exception counts as a provider failure. Being throttled (HTTP 429 for request rate)
    is the provider's fault, because the harness paces to ``pacing_s`` (ADR-0009).
    """


@dataclass(frozen=True, slots=True)
class Size:
    vcpu: float
    memory_gib: float

    def __str__(self) -> str:
        return f"{self.vcpu:g} vCPU / {self.memory_gib:g} GiB"


STANDARD_SIZE = Size(vcpu=2, memory_gib=4)


@dataclass(frozen=True, slots=True)
class Spec:
    """What the harness asks for when it creates a sandbox."""

    name: str
    """Unique resource name, always starting with ``RESOURCE_PREFIX``. Use it (or names
    derived from it) for every resource you create, so cleanup can find them."""
    size: Size = STANDARD_SIZE
    egress: bool = True
    """``False`` means outbound network traffic must be denied for this sandbox."""

    def __post_init__(self) -> None:
        if not self.name.startswith(RESOURCE_PREFIX):
            msg = f"resource name {self.name!r} must start with {RESOURCE_PREFIX!r}"
            raise ValueError(msg)


@dataclass(frozen=True, slots=True)
class Endpoint:
    """How the runner reaches a port exposed from inside a sandbox."""

    url: str
    headers: Mapping[str, str] = field(default_factory=dict)
    """Extra request headers the provider requires, e.g. a preview-link token."""


@dataclass(frozen=True, slots=True)
class ExecResult:
    exit_code: int
    stdout: str
    stderr: str = ""

    @property
    def ok(self) -> bool:
        return self.exit_code == 0


class Adapter[SB, SNAP](ABC):
    """Base class for provider adapters. See ``providers/_template.py`` for a filled-in example."""

    # ---- identity, shown with every result ------------------------------------------------
    name: ClassVar[str]
    """Short, lowercase id used on the command line: ``sbx check <name>``."""
    product: ClassVar[str]
    """Sandbox product, shown as "Provider (product)". Providers with several sandbox
    classes (container, VM, ...) get one adapter per product."""
    owner: ClassVar[str]
    """GitHub handle of whoever keeps this adapter working."""
    access: ClassVar[Access]
    plan: ClassVar[str]
    """Public plan the benchmark runs on, e.g. "free tier"."""
    region: ClassVar[str]
    """Provider region used: the one nearest the us-east runner."""
    start_mode: ClassVar[StartMode]
    size: ClassVar[Size] = STANDARD_SIZE
    """Actual size the provider gives for a standard 2 vCPU / 4 GiB request (nearest shape
    at or above it)."""
    sdk: ClassVar[str] = ""
    """Pinned SDK requirement, e.g. ``"daytona==2.2.0"``; empty for plain REST."""

    # ---- what the provider claims ------------------------------------------------------------
    offers: ClassVar[Mapping[str, str]] = {}
    """Every probe the provider's public docs claim, mapped to the docs URL that claims it."""
    mechanisms: ClassVar[Mapping[str, str]] = {}
    """How an operation is implemented when it isn't a native call, e.g.
    ``{"fork": "snapshot, then create N copies"}``. Shown with the results."""

    # ---- pacing ------------------------------------------------------------------------------
    pacing_s: ClassVar[float] = 0.0
    """Minimum gap between API calls, set from the provider's documented rate limit. The
    harness applies it outside the clock, so throttling while it does is a provider failure."""

    # ---- required ----------------------------------------------------------------------------
    @abstractmethod
    def create(self, spec: Spec) -> SB:
        """Create a sandbox from the provider's default image at ``spec.size`` and return once
        the provider reports it created. The harness times until the first command succeeds."""

    @abstractmethod
    def exec(self, sb: SB, cmd: str, timeout_s: float) -> ExecResult:
        """Run ``cmd`` with ``sh -c`` inside the sandbox and return its exit code and output.

        A non-zero exit is a normal result, not an exception. Raise only when the call itself
        fails (transport error, sandbox gone, timeout)."""

    @abstractmethod
    def destroy(self, sb: SB) -> None:
        """Delete the sandbox. Must not raise if it is already gone."""

    # ---- optional: implement what you offer --------------------------------------------------
    def pause(self, sb: SB) -> None:
        raise NotOffered("pause")

    def resume(self, sb: SB) -> None:
        raise NotOffered("resume")

    def snapshot(self, sb: SB, name: str) -> SNAP:
        """Snapshot a running sandbox and return once the snapshot is usable."""
        raise NotOffered("snapshot")

    def restore(self, snap: SNAP, spec: Spec) -> SB:
        """Create a new sandbox from a snapshot."""
        raise NotOffered("restore")

    def delete_snapshot(self, snap: SNAP) -> None:
        """Delete a snapshot. Must not raise if it is already gone."""
        raise NotOffered("delete_snapshot")

    def fork(self, sb: SB, specs: Sequence[Spec]) -> list[SB]:
        """Make ``len(specs)`` copies of a running sandbox, one per spec, and return them in
        the same order. Any public mechanism counts; declare it in ``mechanisms``."""
        raise NotOffered("fork")

    def expose_port(self, sb: SB, port: int) -> Endpoint:
        """Make ``port`` inside the sandbox reachable from the runner and return how to reach
        it. The probe sends a plain HTTP GET to ``url`` with ``headers``."""
        raise NotOffered("expose_port")

    def ping(self) -> None:
        """Make the cheapest authenticated API call there is. Timed as API RTT (context only)."""
        raise NotOffered("ping")

    def reap(self, prefix: str) -> int:
        """Delete every sandbox and snapshot on the account whose name starts with ``prefix``
        and return how many were deleted. Never touch anything else."""
        raise NotOffered("reap")

    # ---- helpers for adapter authors -----------------------------------------------------------
    @classmethod
    def implements(cls, operation: str) -> bool:
        """Whether this adapter overrides the optional ``operation``."""
        own = getattr(cls, operation, None)
        base = getattr(Adapter, operation, None)
        return own is not None and own is not base

    @staticmethod
    def wait_until(
        predicate: Callable[[], bool],
        *,
        timeout_s: float,
        interval_s: float = 0.25,
        what: str = "condition",
    ) -> None:
        """Poll ``predicate`` until it returns ``True``. Raises ``TimeoutError`` after
        ``timeout_s``. Use this instead of hand-rolled sleep loops."""
        deadline = time.monotonic() + timeout_s
        while True:
            if predicate():
                return
            if time.monotonic() >= deadline:
                msg = f"timed out after {timeout_s:g}s waiting for {what}"
                raise TimeoutError(msg)
            time.sleep(interval_s)

    def __repr__(self) -> str:
        return f"<{type(self).__name__} {self.name} ({self.product})>"
