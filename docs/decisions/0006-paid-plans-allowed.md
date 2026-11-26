# 0006. Accounts may be pay-as-you-go

- **Status:** proposed
- **Date:** 2026-11-26

## Context
METHODOLOGY and the roadmap said accounts run on "free tiers, or credits the provider gives the project". Daytona has no free plan: new accounts are pay-as-you-go with $200 of free compute, billed per second. The adapter declares `plan = "pay-as-you-go"`.

Daytona also gates features by account tier. Its docs say Tier 1 and 2 accounts can reach only "essential services" and can't set network policy per sandbox. Our account reaches arbitrary hosts and accepts `network_block_all`, so it behaves like Tier 3 or higher.

## Decision
Allow any public plan a new customer can sign up for: a free tier, credits, or pay-as-you-go. Each row shows its plan. Where the provider's own tiers change what a probe sees, the tier is stated with the results.

## Alternatives
- **Free tiers only.** Daytona couldn't be benchmarked at all.
- **The cheapest tier for everyone.** On Daytona's Tier 1/2, `internet` and `egress-block` would fail because of the account level, which says nothing about the product.

## Consequences
- Results may not hold for a new Daytona account on Tier 1 or 2: `internet` and `egress-block` would fail there. Listed in [METHODOLOGY §9.3](../METHODOLOGY.md#93-external-validity-how-far-the-results-carry).
- Daily runs cost money on some providers. Payloads and attempt counts stay small (ROADMAP, Risks).
