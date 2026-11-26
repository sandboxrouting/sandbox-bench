"""Every shell script the harness runs inside a sandbox, and the parsers for their output.

Scripts are POSIX ``sh`` and need only ``sha256sum``, ``/dev/shm`` and ``/proc`` (METHODOLOGY
§1); the network probes also look for ``python3``, ``curl``, ``wget`` or ``nc`` (ADR-0008).
Each script prints ``key=value`` lines, and starts with a ``# sbx:<kind> k=v ...`` header so
the fake provider can recognise it without parsing shell.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Final, Literal

from sandbox_bench.benchmark import SHM_BYTES

PINNED_URL: Final = "https://cdnjs.cloudflare.com/ajax/libs/jquery/3.7.1/jquery.min.js"
PINNED_SHA256: Final = "fc9a93dd241f6b045cbff0481cf4e1901becd0e12fb45166a8f17f95823f0b1a"
"""An immutable, versioned CDN file (87,533 bytes): same bytes on cdnjs, jsDelivr and unpkg."""
EGRESS_TARGETS: Final = ("cdnjs.cloudflare.com:80", "1.1.1.1:80")
"""Egress is tried by name and by literal IP: blocking DNS alone doesn't block traffic."""
HTTP_PORT: Final = 8080

_DIR = 'D="${HOME:-/tmp}/.sbx"; mkdir -p "$D" || exit 90\n'
"""Files live under $HOME, not /tmp, which is a tmpfs on some images and would hide a
files-only snapshot behind a lost /tmp."""
_DETACH = "S=; command -v setsid >/dev/null 2>&1 && S=setsid\n"
"""setsid + nohup + closed stdio so the process outlives the exec call that started it."""
_HAS = "command -v {0} >/dev/null 2>&1"
_COUNTER_LOOP = (
    'echo $$ > "$1.pid"; i=0; while :; do i=$((i+1)); echo $i > "$1.tmp"; '
    'mv -f "$1.tmp" "$1.counter"; sleep 0.5; done'
)
_HEX64 = re.compile(r"^[0-9a-f]{64}$")


def _script(kind: str, body: str, **args: str | int) -> str:
    header = " ".join([f"# sbx:{kind}", *(f"{k}={v}" for k, v in args.items())])
    return f"{header}\n{_DIR}{body}"


def identify(cmd: str) -> tuple[str, dict[str, str]] | None:
    """The kind and arguments of a script built here, or ``None`` for any other command."""
    first = cmd.split("\n", 1)[0]
    if not first.startswith("# sbx:"):
        return None
    kind, *pairs = first.removeprefix("# sbx:").split()
    return kind, {k: v for k, _, v in (p.partition("=") for p in pairs)}


def _read_counter(tag: str) -> str:
    return f"""p=$(cat "$D/{tag}.pid" 2>/dev/null); echo "pid=$p"
if [ -n "$p" ] && [ -r "/proc/$p/stat" ]; then
  s=$(cat "/proc/$p/stat"); s=${{s##*") "}}; set -- $s; echo "start=${{20}}"
  echo "cmdline=$(tr '\\000\\n' '  ' < "/proc/$p/cmdline")"
fi
echo "shm=$(sha256sum /dev/shm/{tag} 2>/dev/null | cut -c1-64)"
echo "counter=$(cat "$D/{tag}.counter" 2>/dev/null)"
"""


def counter_start(tag: str) -> str:
    """Fill a RAM buffer, start the counter loop, wait for its first value, then read it."""
    return _script(
        "counter-start",
        f"head -c {SHM_BYTES} /dev/urandom > /dev/shm/{tag} || exit 91\n{_DETACH}"
        f"$S nohup sh -c '{_COUNTER_LOOP}' sbx-counter \"$D/{tag}\" </dev/null >/dev/null 2>&1 &\n"
        f'n=0; while [ ! -s "$D/{tag}.counter" ] && [ $n -lt 100 ]; do\n'
        "  sleep 0.1; n=$((n+1))\ndone\n" + _read_counter(tag),
        tag=tag,
    )


def counter_read(tag: str) -> str:
    return _script("counter-read", _read_counter(tag), tag=tag)


def write_random(name: str, size: int) -> str:
    body = f'head -c {size} /dev/urandom > "$D/{name}" || exit 91\n' + _hash(name)
    return _script("write", body, name=name, size=size)


def hash_file(name: str) -> str:
    return _script("hash", _hash(name), name=name)


def _hash(name: str) -> str:
    return f'echo "sha256=$(sha256sum "$D/{name}" 2>/dev/null | cut -c1-64)"\n'


BOOT: Final = _script(
    "boot",
    'echo "uptime=$(cut -d" " -f1 /proc/uptime)"\n'
    'echo "boot_id=$(cat /proc/sys/kernel/random/boot_id)"\n',
)


def http_serve(port: int, token: str) -> str:
    """Serve ``token`` on ``port`` from python3's http.server, else an ``nc`` loop, and wait
    until the port is listening according to ``/proc/net/tcp``."""
    nc_loop = (
        'while :; do printf "HTTP/1.0 200 OK\\r\\nContent-Length: %s\\r\\nConnection: close'
        '\\r\\n\\r\\n%s" ${#1} "$1" | { nc -l -p "$2" || nc -l "$2" || sleep 1; }; done'
    )
    body = f"""mkdir -p "$D/www" && cd "$D/www" && printf %s {token} > index.html || exit 90
{_DETACH}if {_HAS.format("python3")}; then srv=python3
  $S nohup python3 -m http.server {port} </dev/null >/dev/null 2>&1 &
elif {_HAS.format("nc")}; then srv=nc
  $S nohup sh -c '{nc_loop}' sbx-http {token} {port} </dev/null >/dev/null 2>&1 &
else echo server=none; exit 92; fi
echo "server=$srv"; x=$(printf %04X {port}); n=0
while [ $n -lt 50 ]; do
  grep -Eq ":$x [0-9A-F]+:0000 0A" /proc/net/tcp /proc/net/tcp6 2>/dev/null && exit 0
  sleep 0.2; n=$((n+1))
done
echo listening=no; exit 93
"""
    return _script("serve", body, port=port, token=token)


def download(url: str = PINNED_URL) -> str:
    py = "import sys, urllib.request as u; u.urlretrieve(sys.argv[1], sys.argv[2])"
    body = f"""f="$D/download"; rm -f "$f"
if {_HAS.format("curl")}; then tool=curl; curl -fsSL -m 50 -o "$f" '{url}'
elif {_HAS.format("wget")}; then tool=wget; wget -q -T 50 -O "$f" '{url}'
elif {_HAS.format("python3")}; then tool=python3; python3 -c '{py}' '{url}' "$f"
else echo tool=none; exit 92; fi
echo "rc=$?"; echo "tool=$tool"; echo "sha256=$(sha256sum "$f" 2>/dev/null | cut -c1-64)"
"""
    return _script("download", body, url=url)


def egress_check(targets: tuple[str, ...] = EGRESS_TARGETS) -> str:
    """Send one plain HTTP request to each ``host:port`` and report whether any response byte
    came back. Some providers accept the TCP handshake and then drop the traffic, so only a
    response counts as open. python3 exits 0 (response), 6 (DNS failed), 7 (connect failed)
    or 8 (connected, no response); curl reports its own code plus the HTTP status. ADR-0004."""
    py = (
        'import socket, sys\nh, p = sys.argv[1].rsplit(":", 1)\n'
        "try: s = socket.create_connection((h, int(p)), 5)\n"
        "except socket.gaierror: sys.exit(6)\nexcept OSError: sys.exit(7)\n"
        "try:\n s.settimeout(5)\n"
        ' s.sendall(b"HEAD / HTTP/1.0\\r\\nHost: " + h.encode() + b"\\r\\n\\r\\n")\n'
        " sys.exit(0 if s.recv(1) else 8)\nexcept OSError: sys.exit(8)"
    )
    body = f"""if {_HAS.format("python3")}; then tool=python3
elif {_HAS.format("curl")}; then tool=curl
else echo tool=none; exit 0; fi
echo "tool=$tool"; n=0
for t in {" ".join(targets)}; do
  n=$((n+1))
  if [ "$tool" = python3 ]; then python3 -c '{py}' "$t"; echo "rc$n=$?"
  else c=$(curl -s -o /dev/null -m 10 --connect-timeout 5 -w '%{{http_code}}' "http://$t/")
    echo "rc$n=$?"; echo "http$n=$c"; fi
done
"""
    return _script("egress", body, targets=",".join(targets))


# ---- parsers: tolerant of any output, they never raise --------------------------------------
def parse(out: str) -> dict[str, str]:
    """``key=value`` lines into a dict; other lines are ignored, the last value wins."""
    pairs = (line.partition("=") for line in out.splitlines() if "=" in line)
    return {k.strip(): v.strip() for k, _, v in pairs}


def sha256(out: str) -> str | None:
    value = parse(out).get("sha256", "")
    return value if _HEX64.match(value) else None


def _int(value: str | None) -> int | None:
    return int(value) if value and value.isdigit() else None


@dataclass(frozen=True, slots=True)
class CounterRead:
    """One read of the counter process (METHODOLOGY §3)."""

    pid: int | None
    start: int | None
    """Field 22 of ``/proc/<pid>/stat``: start time in clock ticks since boot."""
    cmdline: str
    shm: str | None
    counter: int | None

    @classmethod
    def parse(cls, out: str) -> CounterRead:
        kv = parse(out)
        shm = kv.get("shm", "")
        return cls(
            pid=_int(kv.get("pid")),
            start=_int(kv.get("start")),
            cmdline=kv.get("cmdline", ""),
            shm=shm if _HEX64.match(shm) else None,
            counter=_int(kv.get("counter")),
        )


Egress = Literal["blocked", "open", "unknown"]


def _egress_one(tool: str, rc: int | None, http: str) -> Egress:
    if rc is None:
        return "unknown"
    if tool == "python3":
        return "open" if rc == 0 else "blocked" if rc in {6, 7, 8} else "unknown"
    if http.strip("0"):
        return "open"
    # DNS, connect, timeout, empty reply, receive failure: no response came back.
    return "blocked" if rc in {6, 7, 28, 52, 56} else "unknown"


def parse_egress(out: str) -> Egress:
    """``open`` if any target answered, ``blocked`` only if every target was tried and none
    answered. A missing tool or an unexpected exit is ``unknown``, never ``blocked``."""
    kv = parse(out)
    tool = kv.get("tool", "")
    if tool not in {"python3", "curl"}:
        return "unknown"
    results = [
        _egress_one(tool, _int(kv.get(f"rc{n}")), kv.get(f"http{n}", ""))
        for n in range(1, len(EGRESS_TARGETS) + 1)
    ]
    if "open" in results:
        return "open"
    return "blocked" if all(r == "blocked" for r in results) else "unknown"
