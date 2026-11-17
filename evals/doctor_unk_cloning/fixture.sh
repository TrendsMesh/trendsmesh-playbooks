#!/bin/bash
# Workspace for this case: the engine shim (./tm.sh), no run folder, made-up ElevenLabs and Replicate keys, and
# the providers' answers to the doctor's key check: both keys work (_lib/provider_answers.sh).
set -euo pipefail
bash "$(dirname "${BASH_SOURCE[0]}")/../_lib/scaffold.sh" none
bash "$(dirname "${BASH_SOURCE[0]}")/../_lib/provider_answers.sh" works
