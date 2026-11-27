#!/usr/bin/env bash
# Print the region label for SBX_RUNNER_REGION on a GitHub-hosted runner (ADR-0010).
# GitHub-hosted runners are Azure VMs and GitHub doesn't pin their region, so ask the Azure
# instance metadata service. Prints e.g. "Azure southcentralus (GitHub-hosted)", or
# "GitHub-hosted, region unknown" if the service doesn't answer.
set -uo pipefail
region=$(curl -fsS -m 3 -H Metadata:true \
  "http://169.254.169.254/metadata/instance/compute/location?api-version=2021-02-01&format=text" \
  || true)
if [ -n "$region" ]; then printf 'Azure %s (GitHub-hosted)\n' "$region"
else echo "GitHub-hosted, region unknown"; fi
