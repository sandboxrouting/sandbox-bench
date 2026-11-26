# 0002. Daytona: a fresh SDK client after 240 s idle

- **Status:** accepted
- **Date:** 2026-11-26

## Context
The Daytona SDK (`daytona==2.2.0`, sync v0) pools its HTTP connections to the toolbox proxy. After a long idle gap, the next command on a pooled connection fails with a connection reset. On the network we tested from, gaps up to 300 s always worked (8 of 8 trials), and gaps of 330 s or more always failed (10 of 10); an earlier run also failed at 310 s (2026-11-26).

The reset doesn't come from Daytona. It comes back within 1–2 ms, while the round trip to Daytona's proxy is about 125 ms, so a NAT router or firewall near the client generated it after dropping the idle connection's state. The same idle connection survived 900 s from a cloud VM. The SDK is what makes this fail rather than recover:
- its sockets have no TCP keepalive, which would keep the connection's state alive;
- its retry for stale connections covers a clean close but not a reset.

With TCP keepalive at 60 s, every trial passed.

The benchmark creates this gap itself: a Daytona snapshot can take minutes (7.6 s to 449 s observed), so the restore that follows it is the first command in a long time. Without a workaround, `snapshot-keeps-files` failed on a dead connection, even though the snapshot itself worked.

## Decision
After 240 s without a command, `create` and `restore` build a new SDK client (3.5 ms, no network call) for the new sandbox. Nothing is retried. See `STALE_AFTER_S` in `providers/daytona.py`.

The SDK's missing keepalive is a finding that users hit too, on any network with a short idle timeout. The workaround is removed once an SDK that keeps connections alive or retries the reset is pinned.

## Alternatives
- **Count the reset as a Daytona failure.** The SDK could handle it, and a real user would hit it. But the drop itself happens in the runner's network, so whether Daytona fails would depend on where we run from, and `snapshot-keeps-files` would measure connection handling instead of snapshots.
- **Turn on TCP keepalive in the SDK's pool.** This fixes the cause, but only by reaching into the SDK's private attributes, which can break on any SDK update.
- **Retry on a reset.** This would break the adapter rule against retries, and it would hide resets everywhere, not just after a gap.
- **A fresh client before every create and restore.** There's no magic number, but every Start would pay a new connection setup (tens of ms), which makes Daytona look slower than it is.
- **Keep connections warm with a ping during long operations.** This sends traffic a user wouldn't, inside the clock.

## Consequences
- Restore includes building the client. That costs about 3.5 ms, so it doesn't change the Restore median.
- A sandbox created *before* a long gap keeps its old client and can still hit a reset. That counts as a Daytona failure.
- Listed in [METHODOLOGY §9.2](../METHODOLOGY.md#92-internal-validity-is-it-the-provider-or-us).
