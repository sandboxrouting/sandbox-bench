"""internet, exposed-port and egress-block.

Each probe runs isolated, so a broken ``expose_port`` fails only ``exposed-port``. The
egress-denied sandbox is a second create; when it is the attempt's only create it is timed as
Start with ``default_create=False``, so it never feeds the Start column.
"""

from __future__ import annotations

import secrets
from typing import Any

import httpx

from sandbox_bench.harness import Check
from sandbox_bench.probes import Context, action, guest
from sandbox_bench.schema import Evidence

ANSWER_WITHIN_S = 30.0
"""How long the runner keeps asking the exposed URL; a provider's proxy may need a moment."""


@action(verdicts=["internet", "exposed-port", "egress-block"], timings=["start"])
def network(h: Context) -> dict[str, Check]:
    out: dict[str, Check] = {}
    if h.wants("internet") or h.wants("exposed-port"):
        sb = h.create()
        if h.wants("internet"):
            out["internet"] = h.isolated(lambda: downloads_pinned_file(h, sb))
        if h.wants("exposed-port"):
            out["exposed-port"] = h.isolated(lambda: port_answers(h, sb))
    if h.wants("egress-block"):
        out["egress-block"] = h.isolated(lambda: egress_blocked(h, h.create(egress=False)))
    return out


def downloads_pinned_file(h: Context, sb: Any) -> Check:
    kv = guest.parse(h.sh(sb, guest.download()).stdout)
    got = guest.sha256(f"sha256={kv.get('sha256', '')}")
    evidence: Evidence = {"tool": kv.get("tool"), "rc": kv.get("rc"), "sha256": got}
    return Check(got == guest.PINNED_SHA256, {**evidence, "expected": guest.PINNED_SHA256})


def port_answers(h: Context, sb: Any) -> Check:
    """Serve a random token in the sandbox; the runner must get it back over the provider's
    URL. The runner retries for ``ANSWER_WITHIN_S``, outside any clock."""
    token = f"sbx-{secrets.token_hex(8)}"
    served = h.sh(sb, guest.http_serve(guest.HTTP_PORT, token))
    server = guest.parse(served.stdout).get("server")
    if not served.ok:
        return Check(False, {"server": server, "exit_code": served.exit_code})
    endpoint = h.expose_port(sb, guest.HTTP_PORT)
    deadline, last = h.env.now() + ANSWER_WITHIN_S, ""
    while True:
        try:
            body = h.env.http_get(endpoint).strip()
        except (httpx.HTTPError, OSError) as exc:
            body, last = "", f"{type(exc).__name__}: {exc}"
        if body == token or h.env.now() >= deadline:
            break
        h.env.sleep(1.0)
    evidence: Evidence = {"server": server, "url": endpoint.url, "body": body[:80]}
    return Check(body == token, evidence, None if body == token else last or "wrong body")


def egress_blocked(h: Context, sb: Any) -> Check:
    out = h.sh(sb, guest.egress_check()).stdout
    kv, result = guest.parse(out), guest.parse_egress(out)
    evidence: Evidence = {"result": result, "targets": list(guest.EGRESS_TARGETS)}
    evidence |= {k: v for k, v in kv.items() if k == "tool" or k[:2] == "rc" or k[:4] == "http"}
    return Check(result == "blocked", evidence)
