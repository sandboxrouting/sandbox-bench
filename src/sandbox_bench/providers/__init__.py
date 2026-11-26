"""Provider adapters, one module per provider.

``load(name)`` finds ``providers/<name>.py`` and returns its single ``Adapter`` subclass, so
adding a provider is adding a file. Modules starting with ``_`` (the template) are skipped.
"""

from __future__ import annotations

import importlib
import inspect
import pkgutil
from typing import Any

from sandbox_bench.adapter import Adapter
from sandbox_bench.benchmark import check_offers

AnyAdapter = Adapter[Any, Any]

OPTIONAL_OPERATIONS = (
    "pause",
    "resume",
    "snapshot",
    "restore",
    "delete_snapshot",
    "fork",
    "expose_port",
    "ping",
    "reap",
)


def available() -> list[str]:
    """Names of every provider module, sorted."""
    return sorted(m.name for m in pkgutil.iter_modules(__path__) if not m.name.startswith("_"))


def adapter_class(name: str) -> type[AnyAdapter]:
    """The adapter class defined in ``providers/<name>.py``."""
    if name not in available():
        msg = f"unknown provider {name!r}; available: {', '.join(available())}"
        raise LookupError(msg)
    module = importlib.import_module(f"{__name__}.{name}")
    found = [
        obj
        for _, obj in inspect.getmembers(module, inspect.isclass)
        if issubclass(obj, Adapter) and obj is not Adapter and obj.__module__ == module.__name__
    ]
    if len(found) != 1:
        msg = f"providers/{name}.py must define exactly one Adapter subclass, found {len(found)}"
        raise LookupError(msg)
    return found[0]


def validate(cls: type[AnyAdapter]) -> list[str]:
    """Problems with an adapter class's declarations; empty when it is valid."""
    problems = [
        f"missing class attribute {attr!r}"
        for attr in ("name", "product", "owner", "access", "plan", "region", "start_mode")
        if not getattr(cls, attr, None)
    ]
    implemented = {op: cls.implements(op) for op in OPTIONAL_OPERATIONS}
    problems.extend(check_offers(cls.offers, implemented))
    return problems
