# 0002. Daytona: a fresh SDK client after 240 s idle

- **Status:** proposed
- **Date:** 2026-11-26

## Context
The Daytona SDK (`daytona==2.2.0`) keeps HTTP connections to the sandbox proxy alive. The proxy drops them after about 5 idle minutes, and the SDK's next command on a dropped connection fails with a connection reset. In testing, an idle gap of 245 s was fine, and gaps of 310 s and 340 s reset.

The benchmark creates this gap itself: a Daytona snapshot can take minutes (7.6 s to 449 s observed), so the restore that follows it is the first command in a long time. Without a workaround, `snapshot-keeps-files` failed on a dead connection, even though the snapshot itself worked.

## Decision
After 240 s without a command, `create` and `restore` build a new SDK client (3.5 ms, no network call) for the new sandbox. Nothing is retried. See `STALE_AFTER_S` in `providers/daytona.py`.

## Alternatives
- **Count the reset as a Daytona failure.** It is the provider's SDK and proxy, and a real user would hit it. But it would make `snapshot-keeps-files` measure connection handling instead of snapshots.
- **Retry on a reset.** This would break the adapter rule against retries, and it would hide resets everywhere, not just after a gap.
- **Keep connections warm with a ping during long operations.** This sends traffic a user wouldn't, inside the clock.

## Consequences
- Restore includes building the client. That costs about 3.5 ms, so it doesn't change the Restore median.
- A sandbox created *before* a long gap keeps its old client and can still hit a reset. That counts as a Daytona failure.
- Listed in [METHODOLOGY §9.2](../METHODOLOGY.md#92-internal-validity-is-it-the-provider-or-us).
