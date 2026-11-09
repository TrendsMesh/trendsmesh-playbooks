#!/bin/sh
# Tests the PreToolUse key guard with tool calls as Claude Code sends them on stdin: through the
# exact hooks.json command under sh, and guard-secrets.ps1 too when pwsh is on PATH
# (PWSH="pixi exec --spec powershell pwsh" works without installing anything).
set -eu
HERE=$(cd "$(dirname "$0")" && pwd)
ROOT=$(dirname "$HERE")
TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT
fail() { echo "FAIL: $1" >&2; exit 1; }
# Under Git Bash, paths go in as C:/... so that both the sh guard and pwsh can open them.
HEREW=$HERE
if command -v cygpath >/dev/null 2>&1; then TMP=$(cygpath -m "$TMP"); HEREW=$(cygpath -m "$HERE"); fi
export CLAUDE_PLUGIN_DATA="$TMP/home/.claude/plugins/data/trendsmesh-playbooks-TrendsMesh"
mkdir -p "$CLAUDE_PLUGIN_DATA" "$TMP/code" "$TMP/ws/runs/01-refresh-ad"
TOKEN="r8_$(printf 'A%.0s' 1 2 3 4 5 6 7 8 9 10 11 12 13 14 15 16 17 18 19 20 21 22 23 24 25 26 27 28 29 30 31 32 33 34 35 36 37)"

# The hook command exactly as hooks.json has it, with the plugin root filled in.
cmd=$(awk -f "$HERE/json-fields.awk" "$ROOT/hooks/hooks.json" \
  | awk -F '\t' '$1 == "hooks.PreToolUse.0.hooks.0.command" { sub(/^[^\t]*\t/, ""); print }' \
  | sed "s|\${CLAUDE_PLUGIN_ROOT}|$ROOT|g")
[ -n "$cmd" ] || fail "no PreToolUse command in hooks.json"

json() {  # cwd, tool_name, tool_input
  printf '{"session_id":"s","transcript_path":"/t.jsonl","cwd":"%s","hook_event_name":"PreToolUse","tool_name":"%s","tool_input":%s}' "$1" "$2" "$3"
}
run_sh() { json "$@" | sh -c "$cmd" || fail "hook exited non-zero: $2 $3"; }
run_ps() { json "$@" | $PWSH -NoProfile -Command "& ([scriptblock]::Create([IO.File]::ReadAllText('$HEREW/guard-secrets.ps1')))"; }
check() {  # expect(deny|allow) cwd tool input
  want=$1; shift
  for runner in $RUNNERS; do
    out=$($runner "$@")
    if printf '%s' "$out" | grep -q '"permissionDecision": *"deny"'; then got=deny; else got=allow; fi
    [ "$got" = "$want" ] || fail "$runner: expected $want for $2 $3, got $got ($out)"
    [ "$got" = deny ] || [ -z "$out" ] || fail "$runner: an allowed call printed: $out"
  done
}
RUNNERS=run_sh
if [ -z "${PWSH:-}" ] && command -v pwsh >/dev/null 2>&1; then PWSH=pwsh; fi
[ -n "${PWSH:-}" ] && RUNNERS="run_sh run_ps"
C="$TMP/code"   # ordinary coding, not a TrendsMesh workspace
W="$TMP/ws"     # a TrendsMesh workspace
D="$CLAUDE_PLUGIN_DATA"

# Denied anywhere.
check deny "$C" Read "{\"file_path\":\"$D/secrets.env\"}"
check deny "$C" Bash '{"command":"cat ~/.claude/plugins/data/*/secrets.e*"}'
check deny "$C" Bash '{"command":"cat \"$CLAUDE_PLUGIN_DATA\"/s*.env"}'
check deny "$C" Bash '{"command":"cat \"$TM_PLUGIN_DATA/secrets.env\""}'
check deny "$C" Bash '{"command":"cat ~/.claude/plugins/data/trendsmesh-playbooks-x/secrets.env"}'
check deny "$C" Bash '{"command":"echo $REPLICATE_API_TOKEN"}'
check deny "$C" Bash '{"command":"test -n \"$CLAUDE_PLUGIN_OPTION_ELEVENLABS_API_KEY\" && echo set"}'
check deny "$C" Glob "{\"pattern\":\"**/*\",\"path\":\"$D\"}"
check deny "$C" Grep "{\"pattern\":\"x\",\"path\":\"$D\"}"
check deny "$C" Read '{"file_path":"/w/notes/secrets.env"}'
check deny "$C" Edit "{\"file_path\":\"/w/a.py\",\"old_string\":\"a\",\"new_string\":\"key = '$TOKEN'\"}"
check deny "$C" Write "{\"file_path\":\"/w/a.txt\",\"content\":\"$TOKEN\"}"
check deny "$C" Read '{"file_path":"C:\\Users\\Łukasz Nowak\\.claude\\plugins\\data\\trendsmesh-playbooks-x\\secrets.env"}'
# A data folder with a Polish letter and no tell-tale name: only the folder itself gives it away.
( export CLAUDE_PLUGIN_DATA="$TMP/Łukasz Nowak/dane"
  check deny "$C" Glob "{\"pattern\":\"**/*\",\"path\":\"$TMP/Łukasz Nowak/dane\"}" )
# Denied in a TrendsMesh workspace only.
check deny "$W" Grep '{"pattern":"REPLICATE","path":"."}'
check deny "$W" Grep '{"pattern":"REPLICATE_API_TOKEN","path":"."}'
check deny "$W" Read '{"file_path":".secrets/api_keys.env"}'
check deny "$W" Bash '{"command":"grep -ri elevenlabs ."}'
check deny "$W" Bash '{"command":"cat .secrets/api_keys.env"}'
# A reader only counts in command position (final review I3), including after a separator or -c.
check deny "$W" Bash '{"command":"cd runs && less replicate_notes.txt"}'
check deny "$W" Bash '{"command":"ls; od -c .secrets/token"}'
check deny "$W" Bash '{"command":"echo $(more elevenlabs.txt)"}'
check deny "$W" Bash '{"command":"sh -c \"cat .secrets/api_keys.env\""}'
check deny "$W" PowerShell '{"command":"type .secrets\\api_keys.env"}'
check deny "$W" PowerShell '{"command":"(Get-Content .secrets/api_keys.env) | Out-String"}'

# Allowed: ordinary coding (the review's examples) and the plugin's own development.
check allow "$C" Bash '{"command":"grep -r token src/"}'
check allow "$C" Grep '{"pattern":"csrfToken","path":"src"}'
check allow "$C" Grep '{"pattern":"secret","path":"."}'
check allow "$C" Read '{"file_path":"/w/src/auth/token.ts"}'
check allow "$C" Bash '{"command":"ls src/auth/token","description":"List the secret token and api key handlers"}'
check allow "$C" Bash '{"command":"sed -n 1,20p src/settings.py"}'
check allow "$C" Bash '{"command":"awk -F, '"'"'{print $1}'"'"' data.csv"}'
check allow "$C" Read '{"file_path":"/w/.secrets.baseline"}'
check allow "$C" Edit '{"file_path":"/w/aws.ts","old_string":"a","new_string":"new AWS.SecretsManager()"}'
check allow "$C" Edit '{"file_path":"/w/vk.c","old_string":"a","new_string":"VK_FORMAT_R8_UNORM"}'
check allow "$C" Edit '{"file_path":"/w/tm/tools/__init__.py","old_string":"a","new_string":"ENV_VARS = {\"replicate_api_token\": \"REPLICATE_API_TOKEN\"}"}'
check allow "$C" Grep '{"pattern":"REPLICATE_API_TOKEN","path":"engine/src"}'
check allow "$C" Bash '{"command":"ls ~/.claude/plugins/data/"}'
# Allowed in a TrendsMesh workspace: the playbook's own work.
check allow "$W" Read '{"file_path":"runs/01-refresh-ad/2026-11-05_ad3/manifest.md"}'
check allow "$W" Bash '{"command":"tm next --run runs/01-refresh-ad/2026-11-05_ad3 --json"}'
check allow "$W" Bash '{"command":"tm tool replicate_run --run runs/x 03_wip/ai/frame1_v01.json --cost 0.1 --json"}'
check allow "$W" Bash '{"command":"tm doctor --outputs creative_brief --mcp trendsmesh=ok,meta=ok --json"}'
check allow "$W" Grep '{"pattern":"hook_rate","path":"runs"}'
# Reader words inside arguments and quoted text are not commands (Polish "od", "more", "less").
check allow "$W" Bash '{"command":"tm tool elevenlabs tts --run runs/x --voice-id abc --text \"Zacznij od dziś\" --cost 300 --json"}'
check allow "$W" Bash '{"command":"tm tool elevenlabs tts --run runs/x --voice-id abc --text \"more or less\" --cost 300 --json"}'
check allow "$W" Bash '{"command":"tm tool elevenlabs history-search --run runs/x \"Pay less, get more\" --json"}'
check allow "$W" Bash '{"command":"tm budget estimate ai_usd 2 --what \"Replicate Veo clip, more motion\""}'
check allow "$W" Bash '{"command":"tm budget estimate ai_usd 2 --what \"Replicate clip, type: B-roll\""}'
# Other tools and broken input pass (fail open).
check allow "$C" WebFetch '{"url":"https://example.com/secrets.env"}'
out=$(printf 'not json' | sh -c "$cmd") || fail "broken input: non-zero exit"
[ -z "$out" ] || fail "broken input printed: $out"

echo "guard-secrets tests passed ($RUNNERS)"
