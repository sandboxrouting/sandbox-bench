"""snapshot-keeps-files and snapshot-keeps-memory: snapshot, then create from it."""

from __future__ import annotations

from sandbox_bench.harness import Check
from sandbox_bench.probes import Context, action


@action(
    verdicts=["snapshot-keeps-files", "snapshot-keeps-memory"],
    timings=["start", "snapshot", "restore"],
)
def snapshot(h: Context) -> dict[str, Check]:
    sb = h.create()
    before = h.start_counter(sb)
    f = h.write_random(sb)
    snap = h.snapshot(sb)  # until the snapshot is usable
    restored = h.restore(snap)  # until the first command succeeds in the new sandbox
    return {
        "snapshot-keeps-files": h.same_file(restored, f),
        "snapshot-keeps-memory": h.counter_continued(restored, before),
    }
