# 0005. Freestyle offers `fork-isolation-x3`

- **Status:** accepted
- **Date:** 2026-11-26

## Context
A probe counts as offered only when the provider's public docs claim it (METHODOLOGY §2). Freestyle has no native fork; its docs describe branching as "snapshot, then create a VM per branch", and the adapter uses that mechanism.

For `fork-keeps-memory`, the claim is direct: a snapshot "is a full memory and disk capture". For `fork-isolation-x3`, no page states that copies are isolated. The closest is a guide that says to "keep each hypothesis in a separate branch when the experiments would interfere" ([reverse-engineer a binary](https://www.freestyle.sh/docs/guides/reverse-engineer-a-binary-with-an-ai-agent#branch-before-patches-and-destructive-experiments)). That implies isolation but doesn't promise it.

## Decision
Offer it for now, citing that guide: each copy is a separate VM created from a snapshot, so isolation is how the mechanism works, and the probe passed live. We ask Freestyle to state in their docs that VMs created from one snapshot share no state. If they won't by launch, the probe becomes n/a for Freestyle.

## Alternatives
- **Mark it not offered.** This is stricter about "the docs claim it". An n/a probe scores the same zero as a failing one, so Freestyle would lose a probe its VMs pass.
- **Offer it with no follow-up.** This leaves the precedent that our reading of a guide is enough.

## Consequences
- Our reading of a guide decides this probe for Freestyle. Listed in [METHODOLOGY §9.1](../METHODOLOGY.md#91-construct-validity-do-the-probes-measure-what-they-say), which also covers how the same judgement applies to other providers.
- If Freestyle's docs ever say copies can share state, this flips to not offered.
