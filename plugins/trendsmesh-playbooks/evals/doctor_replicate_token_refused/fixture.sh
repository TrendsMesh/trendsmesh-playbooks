#!/bin/bash
# Workspace for this case: the engine shim (./tm.sh), no run folder, made-up ElevenLabs and Replicate keys, and
# the doctor's key check answers that Replicate refuses the token (401).
set -euo pipefail
bash "$(dirname "${BASH_SOURCE[0]}")/../_lib/scaffold.sh" none
bash "$(dirname "${BASH_SOURCE[0]}")/../_lib/provider_answers.sh" replicate_refused
