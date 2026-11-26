"""The fixed constants of one benchmark version (METHODOLOGY §2, §4, §5, §8).

Changing anything here changes what scores mean, so it bumps ``VERSION`` after a 7-day notice.
"""

from __future__ import annotations

from collections.abc import Mapping
from types import MappingProxyType
from typing import Final

VERSION: Final = "v0.1"

PROBES: Final[tuple[str, ...]] = (
    "create-exec",
    "file-roundtrip",
    "internet",
    "egress-block",
    "exposed-port",
    "pause-keeps-files",
    "pause-keeps-memory",
    "snapshot-keeps-files",
    "snapshot-keeps-memory",
    "fork-keeps-memory",
    "fork-isolation-x3",
)

REQUIRES: Final[Mapping[str, tuple[str, ...]]] = MappingProxyType(
    {
        "create-exec": (),
        "file-roundtrip": (),
        "internet": (),
        "egress-block": (),
        "exposed-port": ("expose_port",),
        "pause-keeps-files": ("pause", "resume"),
        "pause-keeps-memory": ("pause", "resume"),
        "snapshot-keeps-files": ("snapshot", "restore"),
        "snapshot-keeps-memory": ("snapshot", "restore"),
        "fork-keeps-memory": ("fork",),
        "fork-isolation-x3": ("fork",),
    }
)
"""Optional adapter operations a probe needs. An adapter that offers a probe must implement them."""

ALWAYS_OFFERED: Final[frozenset[str]] = frozenset({"create-exec", "file-roundtrip"})
"""Probes that only use the required operations; every provider is tested on them."""

# ---- scoring -------------------------------------------------------------------------------
ATTEMPTS_PER_RUN: Final = 10
WINDOW: Final = 10
"""A probe's outcome and a timing column's median use the last ``WINDOW`` attempts."""
PASS_THRESHOLD: Final = 9
"""A probe passes when at least this many of the last ``WINDOW`` attempts verified."""

# ---- timeouts (seconds), the same for every provider ----------------------------------------
TIMEOUTS: Final[Mapping[str, float]] = MappingProxyType(
    {
        "create": 120,
        "restore": 120,
        "resume": 120,
        "fork": 120,
        "exec": 60,
        "snapshot": 15 * 60,
        # Not listed in METHODOLOGY because they are never timed as a metric; generous so a
        # slow provider fails on its timed operation, not on cleanup.
        "pause": 120,
        "destroy": 120,
        "delete_snapshot": 120,
        "expose_port": 120,
        "ping": 30,
    }
)

# ---- payloads, identical for every provider ------------------------------------------------
MiB: Final = 1024 * 1024
FILE_BYTES: Final = 10 * MiB
SHM_BYTES: Final = 32 * MiB
COUNTER_INTERVAL_S: Final = 0.5
COUNTER_GAP_S: Final = 2.0
"""Minimum gap between the two counter reads of the memory check (METHODOLOGY §3)."""
FORK_ISOLATION_COPIES: Final = 3
EXEC_SAMPLES: Final = 5


def check_offers(offers: Mapping[str, str], implemented: Mapping[str, bool]) -> list[str]:
    """Return problems with an adapter's ``offers`` declaration; empty when it is valid.

    ``implemented`` maps each optional operation name to whether the adapter overrides it.
    """
    problems: list[str] = []
    for probe, url in offers.items():
        if probe not in REQUIRES:
            problems.append(f"offers unknown probe {probe!r}")
            continue
        if not url.startswith("https://"):
            problems.append(f"{probe}: docs link must be an https URL, got {url!r}")
        problems.extend(
            f"{probe}: offered but {op}() isn't implemented"
            for op in REQUIRES[probe]
            if not implemented.get(op, False)
        )
    return problems
