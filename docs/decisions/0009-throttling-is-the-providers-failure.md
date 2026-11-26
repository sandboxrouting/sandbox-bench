# 0009. Throttling is the provider's failure; a plan limit is ours

- **Status:** accepted
- **Date:** 2026-11-26

## Context
A provider can reject a call with HTTP 429. Attempts that fail on our side (keys, credits, plan limits) are excluded, and anything else fails the provider (METHODOLOGY §5). The two adapters disagreed:
- Daytona's counted every 429 as ours.
- Freestyle's sorted by error code: `LIMIT_EXCEEDED` (a plan limit) as ours, but also `RATE_LIMITED` (throttling), because its code contains "LIMIT".

Providers use 429 for two different things: "slow down" (request rate) and "your plan allows no more of this" (a quota).

## Decision
- **Throttling for request rate is the provider's failure.** The harness paces every provider's calls to its documented rate limit (`pacing_s`), outside the clock. A 429 while we do that means the provider throttled below its own published limit. A provider with no published limit gets `pacing_s = 0`, and any throttling is theirs.
- **A plan limit or quota is ours,** whatever the status code, and the attempt is excluded.

Adapters tell the two apart from the error code or message. Daytona: a 429 is throttling unless the message mentions a quota, credits or billing. Freestyle: the code `RATE_LIMITED` is throttling, and `LIMIT_EXCEEDED` is a plan limit.

## Alternatives
- **Always ours (exclude every 429).** We control the pace, but a provider that throttles harshly would never be penalised, and users do feel it.
- **Always the provider's (fail every 429).** Simple, but a plan quota, or a pacing mistake of ours, would cost the provider points.

## Consequences
- Each adapter must set `pacing_s` from the provider's documentation and link it. A wrong pacing value means unfair failures, so it gets reviewed like an `offers` link.
- Sorting depends on providers' error messages, which can change. Listed in [METHODOLOGY §9.2](../METHODOLOGY.md#92-internal-validity-is-it-the-provider-or-us).
