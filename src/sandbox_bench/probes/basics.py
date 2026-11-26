"""create-exec and file-roundtrip: a new sandbox runs a command, and a file reads back intact."""

from __future__ import annotations

from sandbox_bench.benchmark import EXEC_SAMPLES
from sandbox_bench.harness import Check
from sandbox_bench.probes import Context, action
from sandbox_bench.schema import JsonScalar


@action(verdicts=["create-exec", "file-roundtrip"], timings=["start", "exec"])
def basics(h: Context) -> dict[str, Check]:
    sb = h.create()  # returns once `echo <token>` printed its token: Start's clock boundary
    runs = h.median_of("exec", lambda: h.sh(sb, "true"), EXEC_SAMPLES)
    codes: list[JsonScalar] = [r.exit_code for r in runs]
    f = h.write_random(sb)
    return {
        "create-exec": Check(not any(codes), {"echo": "ok", "true_exit_codes": codes}),
        "file-roundtrip": h.same_file(sb, f),
    }
