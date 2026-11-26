"""Live checks against the real Freestyle API. Needs FREESTYLE_API_KEY; never runs in CI.

Run: ``uv run pytest -m live tests/test_freestyle_live.py``
"""

from __future__ import annotations

import os
import time
from collections.abc import Iterator

import pytest

from sandbox_bench.adapter import Spec
from sandbox_bench.providers.freestyle import Freestyle

pytestmark = [
    pytest.mark.live,
    pytest.mark.skipif(not os.environ.get("FREESTYLE_API_KEY"), reason="FREESTYLE_API_KEY unset"),
]


PREFIX = f"sbx-dev-live{int(time.time()) % 100000}-"


@pytest.fixture
def fs() -> Iterator[Freestyle]:
    adapter = Freestyle()
    try:
        yield adapter
    finally:
        adapter.reap(PREFIX)
        adapter.close()


def test_create_exec_pause_resume_destroy(fs: Freestyle) -> None:
    vm = fs.create(Spec(name=f"{PREFIX}a"))
    assert fs.exec(vm, "echo hi; exit 4", 30).exit_code == 4
    pid = fs.exec(vm, "nohup sleep 1000 >/dev/null 2>&1 & echo $!", 30).stdout.strip()
    fs.pause(vm)
    fs.resume(vm)
    assert fs.exec(vm, f"kill -0 {pid}", 30).ok
    fs.destroy(vm)
    fs.destroy(vm)


def test_snapshot_fork_keep_process(fs: Freestyle) -> None:
    vm = fs.create(Spec(name=f"{PREFIX}p"))
    pid = fs.exec(vm, "nohup sleep 1000 >/dev/null 2>&1 & echo $!", 30).stdout.strip()
    [copy] = fs.fork(vm, [Spec(name=f"{PREFIX}c")])
    assert fs.exec(copy, f"kill -0 {pid}", 30).ok
    fs.destroy(copy)
    fs.destroy(vm)
