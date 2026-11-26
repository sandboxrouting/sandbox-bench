"""fork-keeps-memory and fork-isolation-x3.

The timed fork always makes exactly one child, so the Fork column compares like with like
whether or not a provider also offers isolation. The isolation check is a second, untimed
fork of three children.
"""

from __future__ import annotations

from typing import Any

from sandbox_bench.benchmark import FORK_ISOLATION_COPIES
from sandbox_bench.harness import Check
from sandbox_bench.probes import Context, action
from sandbox_bench.schema import JsonScalar


@action(verdicts=["fork-keeps-memory", "fork-isolation-x3"], timings=["start", "fork"])
def fork(h: Context) -> dict[str, Check]:
    sb = h.create()
    out: dict[str, Check] = {}
    if h.wants("fork-keeps-memory"):
        out["fork-keeps-memory"] = h.isolated(lambda: child_keeps_memory(h, sb))
    if h.wants("fork-isolation-x3"):
        out["fork-isolation-x3"] = h.isolated(lambda: isolated_children(h, sb))
    return out


def child_keeps_memory(h: Context, parent: Any) -> Check:
    before = h.start_counter(parent)
    (child,) = h.fork(parent, 1)  # until the first command succeeds in the child
    check = h.counter_continued(child, before)
    h.destroy(child)  # stay under concurrent-sandbox limits before forking three more
    return check


def isolated_children(h: Context, parent: Any) -> Check:
    """All children run (``h.fork`` waits for a command in each), and a marker written in the
    first is visible there and nowhere else."""
    children = h.fork(parent, FORK_ISOLATION_COPIES, timed=False)
    marker = h.write_random(children[0], 64, name="sbx-marker")
    seen: list[JsonScalar] = [h.file_hash(sb, marker.name) for sb in [parent, *children]]
    ok = marker.sha256 is not None and seen == [None, marker.sha256, None, None]
    return Check(ok, {"marker_sha256": marker.sha256, "seen_in_parent_then_children": seen})
