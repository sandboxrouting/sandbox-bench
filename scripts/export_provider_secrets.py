"""Pass the chosen providers' keys from the `live` environment to the rest of a workflow job.

A secret belongs to provider ``acme`` when its name starts with ``ACME_`` (docs/RUNNER.md).

Used by the live-check and benchmark workflows, after dependencies are installed. That one
step names every provider's secrets in its ``env``; the script passes on only the chosen
providers' ones, so later steps never see another provider's keys:

    env:
      DAYTONA_API_KEY: ${{ secrets.DAYTONA_API_KEY }}
      ...
    run: python3 scripts/export_provider_secrets.py "$PROVIDERS"   # e.g. daytona,freestyle

It appends the matching variables to ``$GITHUB_ENV`` and prints their names, never values.
"""

from __future__ import annotations

import os
import re
import secrets
import sys
from collections.abc import Mapping
from pathlib import Path

PROVIDERS = Path(__file__).resolve().parent.parent / "src" / "sandbox_bench" / "providers"
NAME = re.compile(r"[a-z][a-z0-9_]*")


def provider_secrets(providers: list[str], available: Mapping[str, str]) -> dict[str, str]:
    """The secrets named ``<PROVIDER>_*`` for each provider; every provider needs at least one."""
    found: dict[str, str] = {}
    for provider in providers:
        if not NAME.fullmatch(provider) or not (PROVIDERS / f"{provider}.py").is_file():
            msg = f"unknown provider {provider!r}"
            raise ValueError(msg)
        prefix = f"{provider.upper()}_"
        mine = {name: value for name, value in available.items() if name.startswith(prefix)}
        if not mine:
            msg = f"no {prefix}* secrets given to this step; add them to its env and to `live`"
            raise ValueError(msg)
        found.update(mine)
    return found


def env_file(values: Mapping[str, str]) -> str:
    """``$GITHUB_ENV`` lines, with a random delimiter so any value is passed through intact."""
    lines = []
    for name, value in sorted(values.items()):
        delimiter = f"EOF_{secrets.token_hex(16)}"
        lines.append(f"{name}<<{delimiter}\n{value}\n{delimiter}\n")
    return "".join(lines)


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        sys.stderr.write("usage: export_provider_secrets.py PROVIDER[,PROVIDER...]\n")
        return 2
    providers = [p.strip() for p in argv[1].split(",") if p.strip()]
    try:
        values = provider_secrets(providers, os.environ)
    except ValueError as exc:
        sys.stderr.write(f"::error::{exc}\n")
        return 1
    with Path(os.environ["GITHUB_ENV"]).open("a", encoding="utf-8") as env:
        env.write(env_file(values))
    sys.stdout.write(f"passing {', '.join(sorted(values))} to later steps\n")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
