#!/usr/bin/env bash
# Run the benchmark and publish the result to the results repo (docs/RUNNER.md, ADR-0010).
# Used by the manual "Benchmark run" workflow today, and by the planned daily systemd timer.
#
# 1. Update the harness checkout to the tip of main (unless SBX_UPDATE=0) and sync its
#    locked dependencies.
# 2. Run every configured provider once (`sbx run`), writing one RunRecord JSON.
# 3. Commit the raw record to the results repo, rebuild its tables with `sbx report`,
#    and push.
#
# Configuration comes from the environment (systemd loads it from /etc/sandbox-bench/env):
#   SBX_HOME          harness checkout              (default: ~/sandbox-bench)
#   SBX_RESULTS       results repo checkout         (default: ~/sandbox-bench-results)
#   SBX_PROVIDERS     comma-separated providers     (required, e.g. "daytona,freestyle")
#   SBX_RUNNER_REGION runner region label           (default: us-east)
#   SBX_PUSH          set to 0 to skip `git push`   (default: 1)
#   SBX_UPDATE        set to 0 to run the checkout as it is, e.g. in CI (default: 1)
#   SBX_COMMIT_NOTE   extra line for the results commit, e.g. who started the run
#   plus each provider's credentials, e.g. DAYTONA_API_KEY, FREESTYLE_API_KEY.
set -euo pipefail

SBX_HOME=${SBX_HOME:-$HOME/sandbox-bench}
SBX_RESULTS=${SBX_RESULTS:-$HOME/sandbox-bench-results}
SBX_RUNNER_REGION=${SBX_RUNNER_REGION:-us-east}
SBX_PUSH=${SBX_PUSH:-1}
SBX_UPDATE=${SBX_UPDATE:-1}
SBX_COMMIT_NOTE=${SBX_COMMIT_NOTE:-}
: "${SBX_PROVIDERS:?set SBX_PROVIDERS, e.g. daytona,freestyle}"
export SBX_RUNNER_REGION

log() { printf '%s %s\n' "$(date -u +%FT%TZ)" "$*" >&2; }

# One run at a time, even if a previous run is still going.
exec 9>"${XDG_RUNTIME_DIR:-/tmp}/sandbox-bench.lock"
flock -n 9 || { log "another run holds the lock; skipping"; exit 0; }

if [ "$SBX_UPDATE" = 1 ]; then
  log "updating harness in $SBX_HOME"
  git -C "$SBX_HOME" fetch --quiet origin main
  git -C "$SBX_HOME" checkout --quiet --detach origin/main
fi
(cd "$SBX_HOME" && uv sync --frozen --no-dev --quiet)

git -C "$SBX_RESULTS" pull --quiet --ff-only

out="$SBX_RESULTS/runs"  # `sbx run` adds YYYY/MM/DD/<run_id>.json itself
mkdir -p "$out"

log "running providers: $SBX_PROVIDERS"
status=0
(cd "$SBX_HOME" && uv run --frozen --no-dev sbx run --providers "$SBX_PROVIDERS" --out "$out") || status=$?
# A provider failing is a result, not a reason to drop the record: `sbx run` exits non-zero
# only for harness errors, and even then we keep whatever it wrote and still report.
if [ "$status" -ne 0 ]; then
  log "sbx run exited with $status; publishing whatever it recorded"
fi

log "rebuilding tables"
(cd "$SBX_HOME" && uv run --frozen --no-dev sbx report "$SBX_RESULTS/runs" --out "$SBX_RESULTS/board")

harness_sha=$(git -C "$SBX_HOME" rev-parse --short HEAD)
git -C "$SBX_RESULTS" add runs board
if git -C "$SBX_RESULTS" diff --cached --quiet; then
  log "nothing new to commit"
else
  msg="run $(date -u +%F) (harness $harness_sha)"
  if [ -n "$SBX_COMMIT_NOTE" ]; then msg=$(printf '%s\n\n%s' "$msg" "$SBX_COMMIT_NOTE"); fi
  git -C "$SBX_RESULTS" commit --quiet -m "$msg"
  if [ "$SBX_PUSH" = 1 ]; then
    git -C "$SBX_RESULTS" push --quiet
  fi
fi
log "done (sbx run exit $status)"
exit "$status"
