"""Guest-script builders and parsers, without running a shell."""

from __future__ import annotations

import pytest

from sandbox_bench.probes import guest


def test_identify_reads_the_header() -> None:
    assert guest.identify(guest.write_random("f", 10)) == ("write", {"name": "f", "size": "10"})
    assert guest.identify(guest.BOOT) == ("boot", {})
    assert guest.identify("echo hi") is None


def test_parse_ignores_noise_and_keeps_the_last_value() -> None:
    assert guest.parse("junk\na=1\n b = 2 \na=3\n") == {"a": "3", "b": "2"}


@pytest.mark.parametrize(
    ("out", "expected"),
    [
        ("sha256=" + "a" * 64, "a" * 64),
        ("sha256=" + "A" * 64, None),
        ("sha256=", None),
        ("sha256: e3b0", None),
        ("", None),
    ],
)
def test_sha256(out: str, expected: str | None) -> None:
    assert guest.sha256(out) == expected


def test_counter_read_parse() -> None:
    out = f"pid=42\nstart=1234\ncmdline=sh -c loop\nshm={'b' * 64}\ncounter=7\n"
    assert guest.CounterRead.parse(out) == guest.CounterRead(42, 1234, "sh -c loop", "b" * 64, 7)


def test_counter_read_tolerates_a_dead_process() -> None:
    read = guest.CounterRead.parse("pid=42\nshm=\ncounter=\n")
    assert read == guest.CounterRead(42, None, "", None, None)
    assert guest.CounterRead.parse("garbage") == guest.CounterRead(None, None, "", None, None)


@pytest.mark.parametrize(
    ("out", "expected"),
    [
        ("tool=python3\nrc1=7\nrc2=7", "blocked"),  # connect refused or timed out
        ("tool=python3\nrc1=6\nrc2=7", "blocked"),  # DNS failed, IP refused
        ("tool=python3\nrc1=8\nrc2=8", "blocked"),  # handshake accepted, nothing back
        ("tool=python3\nrc1=6\nrc2=0", "open"),  # DNS blocked but the IP answered
        ("tool=python3\nrc1=0\nrc2=7", "open"),
        ("tool=python3\nrc1=1\nrc2=7", "unknown"),  # python crashed: not evidence
        ("tool=python3\nrc1=7", "unknown"),  # a target wasn't tried
        ("tool=curl\nrc1=6\nhttp1=000\nrc2=7\nhttp2=000", "blocked"),
        ("tool=curl\nrc1=52\nhttp1=000\nrc2=28\nhttp2=000", "blocked"),  # empty reply
        ("tool=curl\nrc1=6\nhttp1=000\nrc2=0\nhttp2=301", "open"),
        ("tool=curl\nrc1=60\nhttp1=000\nrc2=7\nhttp2=000", "unknown"),
        ("tool=none", "unknown"),  # a missing tool never counts as blocked
        ("", "unknown"),
    ],
)
def test_parse_egress(out: str, expected: str) -> None:
    assert guest.parse_egress(out) == expected


def test_scripts_use_their_arguments() -> None:
    assert "8080" in guest.http_serve(8080, "tok")
    assert "tok" in guest.http_serve(8080, "tok")
    assert guest.PINNED_URL in guest.download()
    assert all(t in guest.egress_check() for t in guest.EGRESS_TARGETS)
    assert "/dev/shm/t" in guest.counter_start("t")
    assert "/dev/shm/t" in guest.counter_read("t")
