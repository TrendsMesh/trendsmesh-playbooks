#!/bin/bash
# Workspace for this case: the engine shim (./tm.sh), no run folder, and made-up ElevenLabs and Replicate keys
# (the doctor only checks that they are set; nothing is called with them).
set -euo pipefail
bash "$(dirname "${BASH_SOURCE[0]}")/../_lib/scaffold.sh" none
printf 'ELEVENLABS_API_KEY=xi_EVAL_fake_key_not_real\nREPLICATE_API_TOKEN=r8_EVALfakeTokenNotReal\n' > "$PWD/.tmdata/secrets.env"
chmod 600 "$PWD/.tmdata/secrets.env"
