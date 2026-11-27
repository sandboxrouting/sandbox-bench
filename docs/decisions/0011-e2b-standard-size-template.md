# 0011. E2B runs from its base image, built once at the standard size

- **Status:** proposed
- **Date:** 2026-11-27

## Context
Every sandbox runs at 2 vCPU / 4 GiB, or the nearest shape at or above it, from the provider's default image (METHODOLOGY §1).

On E2B, CPU and memory are fixed when a template is built. Tested 2026-11-27 with `e2b==2.66.0` on a Hobby project:
- A default create (template `base`) gives 2 vCPU / 512 MiB, of which 473 MiB is usable. The [pricing page](https://e2b.dev/pricing) says "the default sandbox has 2 vCPUs and 4 GiB of RAM", but the [billing page](https://docs.e2b.dev/billing#customizing-compute-resources) and the SDK both set memory per template, and the measured default is 512 MiB.
- Sizing at create (`Sandbox.create(cpu_count=2, memory_mb=4096)`) is refused: `400: Resizable templates are not enabled for your team`.
- E2B's documented way to get another size is to build a template with `cpu_count` and `memory_mb` ([billing](https://docs.e2b.dev/billing#customizing-compute-resources)). `Template().from_base_image()`, which is E2B's base image `e2bdev/base`, built at 2 vCPU / 4 GiB took 26 s. Sandboxes from it start in about 1.0 s, against 0.8 s for `base`, and are memory restores: their uptime is 3.5 s at the first command.

## Decision
The adapter creates every sandbox from `sandbox-bench-2c4g`: E2B's base image with nothing added, built at 2 vCPU / 4 GiB. It is a fixture kept on the account, built once with `python -m sandbox_bench.providers.e2b build-template`, and rebuilt whenever the `e2b` SDK pin changes. A missing template is an `AccountError`, a setup problem on our side.

## Alternatives
- **Use `base` at 2 vCPU / 512 MiB.** It is the true default, but it is below the standard size, so E2B's state columns (Resume, Restore, Fork) couldn't be ranked against anyone (METHODOLOGY §5), and an 8× smaller memory makes pause, snapshot and fork cheaper to do.
- **Size each sandbox at create.** It is the most direct mapping, but this project can't use it (above).
- **Build the template in every run, named `sbx-…`.** It would follow E2B's base image as it changes, and the reaper would clean it up. But each run would add a build step that can fail on its own, and builds aren't part of what the benchmark measures.

## Consequences
- E2B's Start and Restore are timed on a custom template, not on `base`. If E2B serves `base` from a warmer pool than custom templates, E2B's default create would be somewhat faster than shown (0.8 s against 1.0 s in the test above).
- The image is E2B's base image as of the build, so it can drift from what `base` gives today until the next SDK-pin upgrade rebuilds it.
- Both are listed in [METHODOLOGY §9.3](../METHODOLOGY.md#93-external-validity-how-far-the-results-carry). E2B's row shows its size as 2 vCPU / 4 GiB, and its price is for that size.
