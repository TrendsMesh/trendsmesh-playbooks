#!/bin/bash
# The providers' answers to the doctor's free key check (#66), for a case with made-up keys: runs in the workspace,
# after scaffold.sh. The sandbox must never send a key anywhere, so the engine reads these answers instead of calling
# Replicate or ElevenLabs (tm.providers, TM_PROVIDER_ANSWERS), as ./tm.sh hands .plans.json to `tm offer`.
#   provider_answers.sh <name>      _lib/fixtures/provider_answers/<name>.json; it also writes the made-up keys
set -euo pipefail
LIB="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cp "$LIB/fixtures/provider_answers/$1.json" "$PWD/.provider_answers.json"
printf 'export TM_PROVIDER_ANSWERS="%s"\n' "$PWD/.provider_answers.json" >> "$PWD/.tm-env"
printf 'ELEVENLABS_API_KEY=xi_EVAL_fake_key_not_real\nREPLICATE_API_TOKEN=r8_EVALfakeTokenNotReal\n' > "$PWD/.tmdata/secrets.env"
chmod 600 "$PWD/.tmdata/secrets.env"
