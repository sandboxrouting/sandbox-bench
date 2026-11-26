"""The real guest scripts, run by a real local ``sh``, checked by the real parsers and verifiers.

``LocalShell`` is a test double, not a registered provider: each "sandbox" is a temp HOME, and
every process a test starts is killed on destroy.
"""

from __future__ import annotations

import itertools
import os
import shutil
import signal
import socket
import subprocess
import sys
import threading
import time
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

import httpx
import pytest

from sandbox_bench import probes
from sandbox_bench.adapter import Adapter, Endpoint, ExecResult, Spec
from sandbox_bench.harness import Env, Pacer
from sandbox_bench.probes import Context, guest

pytestmark = [
    pytest.mark.posix_shell,
    pytest.mark.skipif(sys.platform != "linux", reason="needs Linux /proc and /dev/shm"),
]


class LocalShell(Adapter[Path, None]):
    name = "local-shell"
    product = "sh"
    owner = "@sandboxrouting"
    access = "sdk"
    plan = "local"
    region = "local"
    start_mode = "cold"

    def __init__(self, root: Path, path: str | None = None) -> None:
        self.root, self.path = root, path or os.environ.get("PATH", "")
        self.shm: set[str] = set()

    def create(self, spec: Spec) -> Path:
        home = self.root / spec.name
        home.mkdir()
        return home

    def exec(self, sb: Path, cmd: str, timeout_s: float) -> ExecResult:
        if (found := guest.identify(cmd)) and "tag" in found[1]:
            self.shm.add(found[1]["tag"])
        env = {**os.environ, "HOME": str(sb), "PATH": self.path}
        p = subprocess.run(
            ["/bin/sh", "-c", cmd],
            env=env,
            capture_output=True,
            text=True,
            timeout=timeout_s,
            check=False,
        )
        return ExecResult(p.returncode, p.stdout, p.stderr)

    def destroy(self, sb: Path) -> None:
        """Kill every process whose working directory or command line is inside ``sb``."""
        for proc in Path("/proc").glob("[0-9]*"):
            try:
                cwd = os.readlink(proc / "cwd")
                cmdline = (proc / "cmdline").read_bytes().decode(errors="replace")
            except OSError:
                continue
            if cwd.startswith(str(sb)) or str(sb) in cmdline:
                os.kill(int(proc.name), signal.SIGKILL)
        for tag in self.shm:
            Path("/dev/shm", tag).unlink(missing_ok=True)


@pytest.fixture
def shell(tmp_path: Path) -> Iterator[LocalShell]:
    adapter = LocalShell(tmp_path)
    yield adapter
    for home in tmp_path.iterdir():
        adapter.destroy(home)


@pytest.fixture
def tag(tmp_path: Path) -> str:
    return f"sbx-test-{os.getpid()}-{tmp_path.name}"


def context(shell: LocalShell) -> Context:
    env = Env(sleep=lambda s: time.sleep(min(s, 1.2)))  # 1.2 s still spans two counter ticks
    return Context(
        shell, prefix="sbx-t", wanted=(), timings=["start"], env=env, pacer=Pacer(0, env)
    )


def bin_with(tmp_path: Path, *tools: str) -> str:
    """A PATH holding only ``tools`` (plus the basics every script uses)."""
    d = tmp_path / "bin"
    d.mkdir(exist_ok=True)
    for tool in {*tools, "mkdir", "rm", "cut", "sha256sum", "cat", "head"}:
        if (src := shutil.which(tool)) and not (d / tool).exists():
            (d / tool).symlink_to(src)
    return str(d)


def test_counter_start_and_read(shell: LocalShell, tag: str) -> None:
    sb = shell.create(Spec("sbx-a"))
    first = guest.CounterRead.parse(shell.exec(sb, guest.counter_start(tag), 30).stdout)
    assert first.pid
    assert first.start
    assert first.shm
    assert first.counter
    assert "sbx-counter" in first.cmdline
    time.sleep(1.2)
    later = guest.CounterRead.parse(shell.exec(sb, guest.counter_read(tag), 30).stdout)
    assert (later.pid, later.start, later.cmdline, later.shm) == (
        first.pid,
        first.start,
        first.cmdline,
        first.shm,
    )
    assert later.counter is not None
    assert later.counter > first.counter


def test_memory_check_passes_on_a_live_process(
    shell: LocalShell, tag: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(probes, "COUNTER_TAG", tag)
    h = context(shell)
    sb = h.create()
    assert h.start_evidence.keys() == {"uptime", "boot_id"}
    before = h.start_counter(sb)
    check = h.counter_continued(sb, before)
    assert check.ok, check.evidence


def test_memory_check_fails_on_a_restart(
    shell: LocalShell, tag: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A restarted sandbox: the process is gone, the buffer is empty, the counter file stale."""
    monkeypatch.setattr(probes, "COUNTER_TAG", tag)
    h = context(shell)
    sb = h.create()
    before = h.start_counter(sb)
    shell.destroy(sb)
    check = h.counter_continued(sb, before)
    assert not check.ok
    assert check.evidence["shm_sha256"] == [before.shm, None]
    counter = check.evidence["counter"]
    assert isinstance(counter, list)
    assert counter[1] == counter[2]  # stale


def test_file_roundtrip(shell: LocalShell) -> None:
    h = context(shell)
    sb = h.create()
    written = h.write_random(sb, 1024 * 1024)
    assert written.sha256 is not None
    assert (sb / ".sbx" / "sbx-file").stat().st_size == 1024 * 1024
    assert h.same_file(sb, written).ok
    (sb / ".sbx" / "sbx-file").write_bytes(b"changed")
    assert not h.same_file(sb, written).ok
    assert h.file_hash(sb, "missing") is None


def test_download_by_curl_from_a_file_url(shell: LocalShell, tmp_path: Path) -> None:
    src = tmp_path / "pinned"
    src.write_bytes(b"pinned bytes")
    sb = shell.create(Spec("sbx-a"))
    kv = guest.parse(shell.exec(sb, guest.download(src.as_uri()), 30).stdout)
    assert kv["tool"] == "curl"
    assert kv["rc"] == "0"
    expected = subprocess.run(["sha256sum", str(src)], capture_output=True, text=True, check=True)
    assert kv["sha256"] == expected.stdout[:64]


def test_download_without_any_tool(tmp_path: Path) -> None:
    shell = LocalShell(tmp_path, bin_with(tmp_path))
    out = shell.exec(shell.create(Spec("sbx-a")), guest.download(), 30)
    assert (out.exit_code, guest.parse(out.stdout)["tool"]) == (92, "none")


def _closed_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port: int = s.getsockname()[1]
    return port


@contextmanager
def _server(reply: bytes) -> Iterator[str]:
    """A local TCP server that answers every connection with ``reply`` (empty: accept, then
    close without a byte, like a provider's egress sinkhole). Yields ``host:port``."""
    server = socket.socket()
    server.bind(("127.0.0.1", 0))
    server.listen()
    server.settimeout(0.2)
    stop = threading.Event()

    def serve() -> None:
        while not stop.is_set():
            try:
                conn, _ = server.accept()
            except TimeoutError:
                continue
            with conn:
                conn.recv(1024)
                conn.sendall(reply)

    thread = threading.Thread(target=serve, daemon=True)
    thread.start()
    try:
        yield f"127.0.0.1:{server.getsockname()[1]}"
    finally:
        stop.set()
        thread.join()
        server.close()


OK = b"HTTP/1.0 200 OK\r\nContent-Length: 0\r\n\r\n"
UNRESOLVABLE = "sbx-egress-test.invalid:80"


_names = itertools.count()


def _egress(shell: LocalShell, *targets: str) -> str:
    sb = shell.create(Spec(f"sbx-egress-{next(_names)}"))
    out = shell.exec(sb, guest.egress_check(targets), 30).stdout
    return guest.parse_egress(out)


def test_egress_refused_is_blocked(shell: LocalShell) -> None:
    closed = f"127.0.0.1:{_closed_port()}"
    assert _egress(shell, UNRESOLVABLE, closed) == "blocked"


def test_egress_sinkhole_is_blocked(shell: LocalShell) -> None:
    with _server(b"") as sinkhole:
        assert _egress(shell, sinkhole, sinkhole) == "blocked"


def test_egress_answered_is_open(shell: LocalShell) -> None:
    with _server(OK) as target:
        assert _egress(shell, UNRESOLVABLE, target) == "open"  # DNS blocked, IP open


def test_egress_by_curl_when_python_is_missing(tmp_path: Path) -> None:
    shell = LocalShell(tmp_path, bin_with(tmp_path, "curl"))
    closed = f"127.0.0.1:{_closed_port()}"
    with _server(b"") as sinkhole:
        out = shell.exec(shell.create(Spec("sbx-a")), guest.egress_check((sinkhole, closed)), 30)
    assert guest.parse(out.stdout)["tool"] == "curl"
    assert guest.parse_egress(out.stdout) == "blocked"
    with _server(OK) as target:
        assert _egress(shell, closed, target) == "open"


def test_egress_without_a_tool_is_not_blocked(tmp_path: Path) -> None:
    shell = LocalShell(tmp_path, bin_with(tmp_path))
    out = shell.exec(shell.create(Spec("sbx-a")), guest.egress_check(), 30)
    assert guest.parse_egress(out.stdout) == "unknown"


@pytest.mark.parametrize("tool", ["python3", "nc"])
def test_http_serve(tmp_path: Path, tool: str) -> None:
    tools = ["python3"] if tool == "python3" else ["nc", "setsid", "nohup", "grep", "sleep"]
    if not all(shutil.which(t) for t in tools):
        pytest.skip(f"{tool} not installed")
    tools += ["setsid", "nohup", "grep", "sleep", "sh"]
    shell = LocalShell(tmp_path, bin_with(tmp_path, *tools))
    sb = shell.create(Spec("sbx-a"))
    port = _closed_port()
    try:
        out = shell.exec(sb, guest.http_serve(port, "sbx-token"), 30)
        assert out.ok, out
        assert guest.parse(out.stdout)["server"] == tool
        endpoint = Endpoint(f"http://127.0.0.1:{port}/")
        assert httpx.get(endpoint.url, timeout=5).text.strip() == "sbx-token"
    finally:
        shell.destroy(sb)


def test_boot_evidence(shell: LocalShell) -> None:
    kv = guest.parse(shell.exec(shell.create(Spec("sbx-a")), guest.BOOT, 30).stdout)
    assert float(kv["uptime"]) > 0
    assert len(kv["boot_id"]) == 36
