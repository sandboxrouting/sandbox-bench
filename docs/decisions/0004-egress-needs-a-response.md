# 0004. Egress counts as open only if a response comes back

- **Status:** accepted
- **Date:** 2026-11-26

## Context
`egress-block` passes when a sandbox created with outbound traffic denied can't reach the Internet. The first check was a DNS lookup plus a TCP connect, and it was wrong in two ways:
- **Blocking DNS isn't blocking traffic.** A sandbox that can't resolve names but can still reach any IP would have passed.
- **Some blocks accept the connection.** With `network_block_all`, Daytona completes every TCP handshake and then sends nothing back (a sinkhole). A connect-only check reads that as open, so Daytona would have failed a block that works.

## Decision
Send one plain HTTP request to `cdnjs.cloudflare.com:80` (by name) and one to `1.1.1.1:80` (by IP), with 5 s timeouts. Egress is **open** if either sends back one response byte, and **blocked** only if both were tried and neither did. Anything else, such as no tool to test with or an unexpected exit, is **unknown** and fails the probe. See `egress_check` and `parse_egress` in `probes/guest.py`.

Live results on 2026-11-26: Daytona blocked (DNS fails, the IP sinkholes), and Freestyle blocked (DNS fails, the connection to the IP fails).

## Alternatives
- **TCP connect only.** It misreads sinkholes, as above.
- **HTTPS to the pinned file.** This is stricter, but a TLS failure can't tell "blocked" from "a broken CA bundle in the image".
- **Add port 443.** A small step toward "all traffic", planned for v0.2.
- **Ports 80 and 443, plus UDP and IPv6.** Closest to "nothing gets out", but many providers have no IPv6, so telling "blocked" from "doesn't exist" gets complicated.

## Consequences
- Only port 80 over TCP and IPv4 is tested. A block that leaves other ports, UDP or IPv6 open still passes. Listed in [METHODOLOGY §9.1](../METHODOLOGY.md#91-construct-validity-do-the-probes-measure-what-they-say).
- If cdnjs and 1.1.1.1 are both unreachable from a provider for unrelated reasons, a sandbox with egress allowed would read as blocked. `internet` would fail in the same run, which flags it.
