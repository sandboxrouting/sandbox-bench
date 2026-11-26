# 0007. A price the provider doesn't publish is shown as unknown

- **Status:** accepted
- **Date:** 2026-11-26

## Context
The cost columns come from list prices in `pricing/pricing.yaml`, each with a source link and the date it was checked. Freestyle's pricing page gives no rate for a paused VM. It lists storage at $0.000086/GiB-h but doesn't say how much storage a paused VM bills, for example whether its 4 GiB of memory is stored.

## Decision
A price the provider doesn't publish is `null` with a `todo:` saying what is missing, and the tables show "?". We ask the provider and fill it in from their answer or their docs, with the source. We are asking Freestyle about paused VMs.

## Alternatives
- **Estimate it** (e.g. disk plus memory size times the storage rate). This is a number we made up, presented next to numbers they published.
- **Measure it:** pause a VM for a day and read the bill. Real data, but slow, it costs money, and billing is too coarse to be precise.
- **Show n/a.** That reads as "pause isn't offered", which is false.

## Consequences
- Cost columns have gaps until providers answer.
- A reader can't rank Freestyle on paused cost yet.
