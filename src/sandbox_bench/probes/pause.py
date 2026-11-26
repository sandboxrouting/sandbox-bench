"""pause-keeps-files and pause-keeps-memory: pause, then resume."""

from __future__ import annotations

from sandbox_bench.harness import Check
from sandbox_bench.probes import Context, action


@action(verdicts=["pause-keeps-files", "pause-keeps-memory"], timings=["start", "pause", "resume"])
def pause(h: Context) -> dict[str, Check]:
    sb = h.create()
    before = h.start_counter(sb)  # sh loop + /dev/shm buffer (METHODOLOGY §3)
    f = h.write_random(sb)
    h.pause(sb)  # until the call returns
    h.resume(sb)  # until the first command succeeds
    return {
        "pause-keeps-files": h.same_file(sb, f),
        "pause-keeps-memory": h.counter_continued(sb, before),
    }
