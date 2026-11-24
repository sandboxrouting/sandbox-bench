# Governance and fairness policy

People only use a benchmark they trust. This document says, in advance, how we keep sandbox-bench neutral and how vendors and contributors take part.

## 1. Neutrality charter

1. **No pay-to-play.** We never sell placement, logos in result tables, "claimed profiles", early access to data, private benchmarks, or advisory seats.
2. **Funding disclosure.** `FUNDING.md` lists every source of money, credits or infrastructure, with amounts. Donations and grants are welcome, but they never buy influence over methodology.
3. **Conflict-of-interest disclosure.**
   - Every maintainer lists their employer and any commercial ties in `MAINTAINERS.md`.
   - Maintainers recuse themselves from reviewing PRs, disputes or RFCs that affect their employer or a direct competitor's ranking.
   - **This applies to the project's founders too.** Ties to any sandbox, routing or aggregation product must be disclosed prominently.
4. **One harness.** Maintainers own the timing code, workloads, timeouts and scoring. Vendors may contribute *adapters* but cannot change how measurement works (§4).

## 2. Divisions

| Division | Rules | Purpose |
|---|---|---|
| `default` | Public SDK at a pinned version, the standard sandbox spec, a self-serve plan, documented defaults only | The comparable, headline view |
| `optimized` | Any documented, generally available feature or plan, e.g. warm pools, enterprise tier, custom kernel. The configuration is disclosed in full. | Lets vendors show their best case |

Features in beta or preview are tagged `preview` and kept out of `default` rankings.

## 3. Accounts and credits

- By default, the project pays for self-serve accounts.
- Vendors may offer credits, which are disclosed per configuration. Accepting credits never affects inclusion or ranking.
- **Mystery-shopper check.** At least monthly, each configuration that runs on vendor-provided credits or accounts is also measured from an anonymous account the project pays for. If the two differ by more than the confidence intervals allow, we investigate.

## 4. Adapters and vendor contributions

- Each adapter is a thin, readable module that maps our interface to the vendor's **public** SDK. Code paths only available to the benchmark (special endpoints, pre-warming) are prohibited in `default`.
- Vendors may become CODEOWNERS of their own adapter. Every change still needs approval from a non-vendor maintainer.
- Every adapter declares its capabilities, sandbox type, plan and SDK version in `provider.yaml`. A false capability claim fails the capability probes, which is visible to everyone.

## 5. Publication cycle and right of reply

1. **Continuous data** is published automatically. It carries a banner: "automated results, see methodology".
2. **Major releases**, such as a new track, a launch, or a methodology version, go to every affected vendor **7 days before publication** through a private email and a public tracking issue with no numbers in it.
3. **Vendor notes.** Each provider profile has an optional vendor statement of up to 500 characters, displayed as-is and labelled as the vendor's.
4. **Disputes** are filed as public GitHub issues using the `dispute` template. Maintainers acknowledge within 5 working days, and the outcome is recorded in `docs/disputes/`. While a dispute is open, the result stays published and is annotated.

## 6. Anti-gaming and sanctions

We expect people to optimize for the benchmark, and we design for it:

- Workloads use randomized inputs where possible (random file contents, random buffer sizes within a range).
- Accounts are unannounced and rotated, and the mystery-shopper check (§3) applies.
- We watch for behaviour that only appears under benchmark conditions, such as detecting our image or tags.

**Sanctions ladder** (published ahead of time and applied the same way to everyone):

1. Annotate the result.
2. Re-measure from a new anonymous account.
3. Withhold the affected results.
4. Delist the configuration for one release.
5. Publish a disclosure.

## 7. Citation policy (for vendors and press)

You are welcome to quote sandbox-bench results if you include:

- the metric name and division;
- the harness version and date window (e.g. "sandbox-bench v0.1, 2026-12-01 → 12-07");
- a link to the result page.

You may not:

- present a `preview` or `optimized` result as `default`;
- claim an overall "#1" that our pages don't show;
- quote a result while omitting its success rate when the success rate is below 95%.

Repeated misuse is noted publicly on the provider's profile.

## 8. Changing the benchmark (RFCs)

- **New benchmarks** that fit an existing track need a PR with a design note and approval from two maintainers.
- **New tracks, scoring changes and timing-boundary changes** need an RFC in `docs/rfcs/`, open for 14 days. Vendors are pinged and may comment, and maintainers decide.
- **Every accepted change** is logged in `CHANGELOG.md` with its version impact.

## 9. Terms of service

Before a provider is added, a maintainer checks its terms for benchmark-publication ("DeWitt") clauses and records the finding in `provider.yaml`. Where publication is restricted, we ask the vendor for written permission and publish that exchange. We never run probes that would breach acceptable-use terms, such as abusive load or attempts to escape isolation.
