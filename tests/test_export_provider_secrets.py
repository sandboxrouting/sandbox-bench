"""scripts/export_provider_secrets.py: each provider gets only the secrets named after it."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "export_provider_secrets.py"

SECRETS = {
    "DAYTONA_API_KEY": "d-key",
    "DAYTONA_API_URL": "https://example.test/api",
    "FREESTYLE_API_KEY": "f-key\nwith a second line",
    "RESULTS_DEPLOY_KEY": "not for providers",
    "github_token": "not for providers",
}


def run(tmp_path: Path, providers: str) -> tuple[subprocess.CompletedProcess[str], str]:
    env_file = tmp_path / "github_env"
    env_file.touch()
    result = subprocess.run(
        [sys.executable, str(SCRIPT), providers],
        env={"SECRETS_JSON": json.dumps(SECRETS), "GITHUB_ENV": str(env_file)},
        capture_output=True,
        text=True,
        check=False,
    )
    return result, env_file.read_text(encoding="utf-8")


def parse(env_file: str) -> dict[str, str]:
    """Read ``NAME<<DELIM`` blocks back the way the runner does."""
    values: dict[str, str] = {}
    lines = iter(env_file.splitlines())
    for header in lines:
        name, delimiter = header.split("<<")
        body = []
        for line in lines:
            if line == delimiter:
                break
            body.append(line)
        values[name] = "\n".join(body)
    return values


def test_each_provider_gets_only_its_own_secrets(tmp_path: Path) -> None:
    result, env_file = run(tmp_path, "daytona, freestyle")
    assert result.returncode == 0, result.stderr
    assert parse(env_file) == {
        "DAYTONA_API_KEY": "d-key",
        "DAYTONA_API_URL": "https://example.test/api",
        "FREESTYLE_API_KEY": "f-key\nwith a second line",
    }
    assert "d-key" not in result.stdout
    assert "DAYTONA_API_KEY" in result.stdout


def test_a_provider_without_secrets_fails_before_the_run(tmp_path: Path) -> None:
    result, env_file = run(tmp_path, "daytona,fake")
    assert result.returncode == 1
    assert "no secrets named FAKE_*" in result.stderr
    assert env_file == ""


def test_unknown_or_malformed_names_are_refused(tmp_path: Path) -> None:
    for providers in ("acme", "_template", "../daytona", "RESULTS"):
        result, env_file = run(tmp_path, providers)
        assert result.returncode == 1, providers
        assert "unknown provider" in result.stderr
        assert env_file == ""
