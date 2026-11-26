# 0008. Network probes use tools from the default image

- **Status:** accepted
- **Date:** 2026-11-26

## Context
Probes run in the provider's default image (METHODOLOGY §1) and bring nothing of their own beyond `sh` scripts. The core probes need only `sh`, `head`, `cut`, `sha256sum`, `/proc` and `/dev/shm`. A POSIX shell can't speak HTTP or open sockets, so the network probes need a client from the image:
- `internet`: `curl`, else `wget`, else `python3`;
- `egress-block`: `python3`, else `curl`;
- `exposed-port`: `python3 -m http.server`, else an `nc` loop.

## Decision
Use whichever of these the default image has, in that order, and record which one in the evidence. A missing tool fails the probe and never passes it.

## Alternatives
- **Upload a static binary** (e.g. a small Go HTTP client and server) before the probe. This works in any image, but the upload would happen inside or near the clock and adds a harness component every provider must accept.
- **Install a tool with the image's package manager.** This is slow, needs egress (which `egress-block` denies), and differs per distribution.

## Consequences
- A provider whose default image lacks all of these tools fails the network probes even if its network works. Listed in [METHODOLOGY §9.1](../METHODOLOGY.md#91-construct-validity-do-the-probes-measure-what-they-say).
- Different tools can behave differently, for example in timeouts or redirects. The tool is in the evidence, so a dispute can check it.
