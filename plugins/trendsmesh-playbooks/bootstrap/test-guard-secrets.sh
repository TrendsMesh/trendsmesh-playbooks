#!/bin/sh
# Tests the PreToolUse key guard with tool calls as Claude Code sends them on stdin: through the
# exact hooks.json command under sh, and guard-secrets.ps1 too when pwsh is on PATH
# (PWSH="pixi exec --spec powershell pwsh" works without installing anything).
#
# The table below is one call per line: `t <expect> <folder> <tool> <tool_input>`, where expect
# is allow, or deny:<rule> (the rule the block message must name). Every allowed call must print
# nothing; every denied one must name its rule and never repeat a key.
set -eu
HERE=$(cd "$(dirname "$0")" && pwd)
ROOT=$(dirname "$HERE")
TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT
fail() { echo "FAIL: $1" >&2; exit 1; }
# Under Git Bash, paths go in as C:/... so that both the sh guard and pwsh can open them.
HEREW=$HERE ROOTW=$ROOT
if command -v cygpath >/dev/null 2>&1; then TMP=$(cygpath -m "$TMP"); HEREW=$(cygpath -m "$HERE"); ROOTW=$(cygpath -m "$ROOT"); fi
export CLAUDE_PLUGIN_DATA="$TMP/home/.claude/plugins/data/trendsmesh-playbooks-TrendsMesh"
mkdir -p "$CLAUDE_PLUGIN_DATA/envs/abc/envs/default/bin" "$TMP/code" "$TMP/ws/runs/03-organic-ai-video" \
  "$TMP/ws/runs/01-refresh-ad" "$TMP/ws/.secrets" "$TMP/ws2/runs/03-organic-ai-video"
: > "$TMP/ws/.secrets/api_keys.env"
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
run_ps() { json "$@" | CLAUDE_PLUGIN_ROOT=$ROOTW $PWSH -NoProfile -Command "& ([scriptblock]::Create([IO.File]::ReadAllText('$HEREW/guard-secrets.ps1')))"; }
n=0; bad=0
miss() { echo "FAIL: $1" >&2; bad=$((bad + 1)); }
t() {  # expect (allow | deny:<rule>), cwd, tool, input
  want=$1; shift
  n=$((n + 1))
  for runner in $RUNNERS; do
    out=$($runner "$@")
    if printf '%s' "$out" | grep -q '"permissionDecision": *"deny"'; then
      rule=$(printf '%s' "$out" | sed -n 's/.*(rule: \([a-z-]*\)).*/\1/p')
      got="deny:$rule"
    else
      got=allow
    fi
    [ "$got" = "$want" ] || miss "$runner: expected $want for $2 $3, got $got ($out)"
    [ "$got" != allow ] || [ -z "$out" ] || miss "$runner: an allowed call printed: $out"
    case "$out" in *"$TOKEN"*|*r8_AAAA*) miss "$runner: the block message repeats the token: $out" ;; esac
    printf '%s' "$out" | grep -q 'tm doctor' || [ "$got" = allow ] || miss "$runner: no way forward in: $out"
  done
}
says() {  # text the block message must hold, cwd, tool, input (a denied call)
  want=$1; shift
  for runner in $RUNNERS; do
    out=$($runner "$@")
    case "$out" in *"$want"*) ;; *) miss "$runner: the block message for $2 $3 does not say: $want ($out)" ;; esac
  done
}
RUNNERS=run_sh
if [ -z "${PWSH:-}" ] && command -v pwsh >/dev/null 2>&1; then PWSH=pwsh; fi
[ -n "${PWSH:-}" ] && RUNNERS="run_sh run_ps"
C="$TMP/code"   # ordinary coding, not a TrendsMesh workspace
W="$TMP/ws"     # a TrendsMesh workspace that keeps keys in .secrets/ (as the testers' does)
W2="$TMP/ws2"   # a TrendsMesh workspace with no key store of its own
D="$CLAUDE_PLUGIN_DATA"
P="$ROOT"       # the plugin's own source

# --- Denied anywhere -------------------------------------------------------------------------
# secrets.env, the file the keys are kept in: by name, whatever the quoting or the reader.
t deny:secrets-file "$C" Read "{\"file_path\":\"$D/secrets.env\"}"
t deny:secrets-file "$C" Read '{"file_path":"/w/notes/secrets.env"}'
t deny:secrets-file "$C" Read '{"file_path":"C:\\Users\\Łukasz Nowak\\.claude\\plugins\\data\\trendsmesh-playbooks-x\\secrets.env"}'
t deny:secrets-file "$C" Edit "{\"file_path\":\"$D/secrets.env\",\"old_string\":\"a\",\"new_string\":\"b\"}"
t deny:secrets-file "$C" Bash '{"command":"cat ~/.claude/plugins/data/*/secrets.e*"}'
t deny:secrets-file "$C" Bash '{"command":"cat \"$TM_PLUGIN_DATA/secrets.env\""}'
t deny:secrets-file "$C" Bash '{"command":"cat \"$TM_PLUGIN_DATA\"/secr\"\"ets.env"}'
t deny:secrets-file "$C" Bash '{"command":"cat $TM_PLUGIN_DATA/'"'"'secr'"'"'\"ets\".env"}'
t deny:secrets-file "$C" Bash '{"command":"cat ~/x/secr\\ets.env"}'
t deny:secrets-file "$C" Bash '{"command":"cat \"$(echo ~/.claude/plugins/data/trendsmesh-playbooks-x)/secrets.env\""}'
t deny:secrets-file "$C" Bash '{"command":"base64 < ~/.claude/plugins/data/trendsmesh-playbooks-x/secrets.env"}'
t deny:secrets-file "$C" Bash '{"command":"less /Users/x/.claude/plugins/data/trendsmesh-playbooks-x/SECRETS.ENV"}'
t deny:secrets-file "$C" Bash '{"command":"find ~ -name secrets.env -exec cat {} +"}'
t deny:secrets-file "$C" PowerShell '{"command":"Get-Content \"$env:TM_PLUGIN_DATA\\secrets.env\""}'
t deny:secrets-file "$C" PowerShell '{"command":"type %TM_PLUGIN_DATA%\\secrets.env"}'
t deny:secrets-file "$C" PowerShell '{"command":"gc (Join-Path $env:TM_PLUGIN_DATA secrets.env)"}'
t deny:secrets-file "$C" PowerShell '{"command":"gc \"$env:TM_PLUGIN_DATA\\sec`rets.env\""}'
t deny:secrets-file "$C" Grep '{"pattern":"x","path":"/w","glob":"secrets.env"}'
t deny:secrets-file "$C" Glob '{"pattern":"**/secrets.env"}'
t deny:secrets-file "$C" PowerShell '{"command":"type C:\\Users\\x\\.claude\\plugins\\data\\TRENDS~1\\SECRET~1.ENV"}'
# The plugin data folder (where secrets.env is): only its envs/ and pixi/ (the installed tools).
t deny:data-folder "$C" Glob "{\"pattern\":\"**/*\",\"path\":\"$D\"}"
t deny:data-folder "$C" Grep "{\"pattern\":\"x\",\"path\":\"$D\"}"
t deny:data-folder "$C" Read "{\"file_path\":\"$D/install-pixi.log\"}"
t deny:data-folder "$C" Bash '{"command":"cat \"$CLAUDE_PLUGIN_DATA\"/s*.env"}'
t deny:data-folder "$C" Bash '{"command":"cat $TM_PLUGIN_DATA/*"}'
t deny:data-folder "$C" Bash '{"command":"ls -la \"$TM_PLUGIN_DATA\""}'
t deny:data-folder "$C" Bash '{"command":"cat ${TM_PLUGIN_DATA}/en*"}'
t deny:data-folder "$C" Bash '{"command":"cat \"$TM_PLUGIN_DATA\"/{envs,.}/s*"}'
t deny:secrets-file "$C" Bash '{"command":"cat ~/.claude/plugins/data/trendsmesh-playbooks-x/secrets?env"}'
t deny:data-folder "$C" Bash '{"command":"grep -r REPL ~/.claude/plugins/data/trendsmesh-playbooks-x"}'
t deny:data-folder "$C" Bash '{"command":"cat ~/.claude/plugins/data/*/s*"}'
t deny:data-folder "$C" Bash '{"command":"cd ~/.claude/plugins && cat ./data/trendsmesh-playbooks-TrendsMesh/s*"}'
t deny:data-folder "$C" Bash '{"command":"cat \"$(echo $TM_PLUGIN_DATA)/s\"*"}'
t deny:data-folder "$C" Bash '{"command":"python3 -c \"import os; print(os.listdir(os.environ[\\\"TM_PLUGIN_DATA\\\"]))\""}'
t deny:data-folder "$C" PowerShell '{"command":"gc $env:TM_PLUGIN_DATA/s*"}'
t deny:data-folder "$C" PowerShell '{"command":"Get-ChildItem $env:TM_PLUGIN_DATA"}'
t deny:data-folder "$C" PowerShell '{"command":"Get-Content (Join-Path $env:TM_PLUGIN_DATA '"'"'s*'"'"')"}'
t deny:data-folder "$C" PowerShell '{"command":"type %TM_PLUGIN_DATA%\\s*"}'
# The folder that holds every plugin's data folder.
t deny:data-folder "$C" Bash '{"command":"ls ~/.claude/plugins/data/"}'
t deny:data-folder "$C" PowerShell '{"command":"dir C:\\Users\\x\\.claude\\plugins\\data\\TRENDS~1"}'
t deny:data-folder "$C" Bash '{"command":"cd ~/.claude/plugins/data && cat */s*"}'
t deny:data-folder "$C" Bash '{"command":"find ~/.claude/plugins/data -name '"'"'s*.env'"'"' -exec cat {} +"}'
t deny:data-folder "$C" Grep "{\"pattern\":\"REPLICATE\",\"path\":\"$TMP/home/.claude/plugins/data\",\"output_mode\":\"content\"}"
t deny:data-folder "$C" PowerShell '{"command":"Get-ChildItem -Recurse $HOME\\.claude\\plugins\\data | Get-Content"}'
# A data folder with a Polish letter and no tell-tale name: only the folder itself gives it away.
( export CLAUDE_PLUGIN_DATA="$TMP/Łukasz Nowak/dane"
  t deny:data-folder "$C" Glob "{\"pattern\":\"**/*\",\"path\":\"$TMP/Łukasz Nowak/dane\"}" )
# envs/ and pixi/ are no way in either (issue #62): only the programs guard-programs.txt lists.
t deny:data-folder "$C" Bash '{"command":"cat \"$TM_PLUGIN_DATA/envs/../s\"*"}'
t deny:data-folder "$C" Bash '{"command":"cd \"$TM_PLUGIN_DATA/envs\" && cat ../s*"}'
t deny:data-folder "$C" Bash '{"command":"pushd $TM_PLUGIN_DATA/pixi"}'
t deny:data-folder "$C" Bash '{"command":"D=$TM_PLUGIN_DATA/envs; cat $(dirname $D)/s*"}'
t deny:data-folder "$C" PowerShell '{"command":"Get-Content \"$(Split-Path $env:TM_PLUGIN_DATA\\envs)\\s*\""}'
t deny:data-folder "$C" PowerShell '{"command":"Set-Location $env:TM_PLUGIN_DATA\\envs"}'
t deny:data-folder "$C" Read "{\"file_path\":\"$D/envs/abc/../../install-pixi.log\"}"
t deny:data-folder "$C" Bash '{"command":"cat \"$TM_PLUGIN_DATA\"/envs/{..,x}/s*"}'
t deny:data-folder "$C" Bash '{"command":"D=$TM_PLUGIN_DATA/envs; cat $D/../s*"}'
t deny:data-folder "$C" Bash '{"command":"ln -s \"$TM_PLUGIN_DATA/envs\" e && cat e/../s*"}'
t deny:data-folder "$C" Bash '{"command":"cat \"$TM_PLUGIN_DATA/pixi/config.toml\""}'
t deny:data-folder "$C" Bash '{"command":"ls \"$TM_PLUGIN_DATA/envs\""}'
t deny:data-folder "$C" Bash '{"command":"cat $TM_PLUGIN_DATA/envs/abc/envs/base/lib/python3.11/site.py"}'
t deny:data-folder "$C" Bash '{"command":"$TM_PLUGIN_DATA/envs/abc/envs/base/bin/python3.11 x.py"}'
t deny:data-folder "$C" Bash '{"command":"$TM_PLUGIN_DATA/envs/abc/envs/base/bin/ffmpegx -version"}'
t deny:data-folder "$C" Bash '{"command":"cat $TM_PLUGIN_DATA/envs/abc/envs/base/bin/ffmpeg/../../../../s*"}'
t deny:data-folder "$C" Bash '{"command":"cat $TM_PLUGIN_DATA/envs/.?/envs/base/bin/ffmpeg"}'
t deny:data-folder "$C" Bash '{"command":"cat $TM_PLUGIN_DATA/envs/[.]/envs/base/bin/ffmpeg"}'
t deny:data-folder "$C" Bash '{"command":"ls $TM_PLUGIN_DATA/envs/*/envs/*/bin/ff*"}'
t deny:data-folder "$C" Bash '{"command":"ls $TM_PLUGIN_DATA/envs/*/envs/*/bin/"}'
t deny:data-folder "$C" Glob "{\"pattern\":\"**/ffmpeg\",\"path\":\"$D/envs\"}"
t deny:data-folder "$C" Grep "{\"pattern\":\"x\",\"path\":\"$D/pixi\"}"
t deny:data-folder "$C" Read "{\"file_path\":\"$D/envs/abc/conda-meta/pixi\"}"
t deny:data-folder "$C" Read "{\"file_path\":\"$D/remotion/package.json\"}"
t deny:data-folder "$C" PowerShell '{"command":"Get-ChildItem $env:TM_PLUGIN_DATA\\envs -Recurse"}'
# Climbing out of one of those programs, or moving into the data folder, is denied too.
t deny:data-climb "$C" Bash '{"command":"cd \"$(dirname \"$TM_PLUGIN_DATA/pixi/bin/pixi\")\" && cat ../../s*"}'
t deny:data-climb "$C" Bash '{"command":"pushd $TM_PLUGIN_DATA/pixi/bin/pixi"}'
t deny:data-climb "$C" Bash '{"command":"D=$TM_PLUGIN_DATA/pixi/bin/pixi; cat $(dirname $D)/../../s*"}'
t deny:data-climb "$C" PowerShell '{"command":"Get-Content \"$(Split-Path (Split-Path $env:TM_PLUGIN_DATA\\pixi\\bin\\pixi.exe))\\..\\s*\""}'
t deny:data-climb "$C" PowerShell '{"command":"Set-Location $env:TM_PLUGIN_DATA\\pixi\\bin\\pixi.exe"}'
t deny:data-climb "$C" Bash '{"command":"D=$TM_PLUGIN_DATA/pixi/bin/pixi; cat $D/../../../s*"}'
t deny:data-climb "$C" Bash '{"command":"ln -s \"$TM_PLUGIN_DATA/pixi/bin/pixi\" p && cat p/../../../s*"}'
t deny:data-climb "$C" Bash '{"command":"realpath $TM_PLUGIN_DATA/envs/abc/envs/base/bin/python"}'
# A recursive read of a folder above the data folder (home, ~/.claude, ~/.claude/plugins).
t deny:data-parent "$C" Bash '{"command":"grep -rh r8_ ~/.claude"}'
t deny:data-parent "$C" Bash '{"command":"tar cf - -C ~/.claude/plugins data | tar xOf -"}'
t deny:data-parent "$C" Bash '{"command":"cp -R ~/.claude/plugins /tmp/d"}'
t deny:data-parent "$C" Bash '{"command":"grep -r REPLICATE ~"}'
t deny:data-parent "$C" Bash "{\"command\":\"rg -uu token $TMP/home\"}"
t deny:data-parent "$C" Grep "{\"pattern\":\"x\",\"path\":\"$TMP/home\"}"
t deny:data-parent "$TMP/home" Grep '{"pattern":"x"}'
t deny:data-parent "$TMP/home" Bash '{"command":"grep -r x ."}'
# A glob inside ~/.claude/plugins can reach the data folder.
t deny:plugins-glob "$C" Bash '{"command":"cat ~/.claude/plugins/*/*/s*"}'
t deny:plugins-glob "$C" Bash '{"command":"grep -r token ~/.claude/*/data"}'
# The key variables, by name, in any quoting; also case-blind where Windows reads them so.
t deny:key-variable "$C" Bash '{"command":"echo $REPLICATE_API_TOKEN"}'
t deny:key-variable "$C" Bash '{"command":"test -n \"$CLAUDE_PLUGIN_OPTION_ELEVENLABS_API_KEY\" && echo set"}'
t deny:key-variable "$C" Bash '{"command":"printenv ELEVENLABS_API_KEY | head -c 4"}'
t deny:key-variable "$C" Bash '{"command":"eval \"echo \\$REPLI\"\"CATE_API_TOKEN\""}'
t deny:key-variable "$C" PowerShell '{"command":"$env:Replicate_Api_Token.Length"}'
t deny:key-variable "$C" PowerShell '{"command":"[Environment]::GetEnvironmentVariable(\"REPLICATE_API_TOKEN\")"}'
t deny:key-variable "$C" PowerShell '{"command":"cmd /c echo %elevenlabs_api_key%"}'
t deny:key-variable "$W" Grep '{"pattern":"REPLICATE_API_TOKEN","path":"runs"}'
# A Replicate token, in any field (and never repeated in the message).
t deny:token "$C" Edit "{\"file_path\":\"/w/a.py\",\"old_string\":\"a\",\"new_string\":\"key = '$TOKEN'\"}"
t deny:token "$C" Write "{\"file_path\":\"/w/a.txt\",\"content\":\"$TOKEN\"}"
t deny:token "$C" Bash "{\"command\":\"curl -H 'Authorization: Bearer $TOKEN' https://api.replicate.com/v1/account\"}"
# A dump of the whole environment.
t deny:env-dump "$C" Bash '{"command":"env"}'
t deny:env-dump "$C" Bash '{"command":"env | grep -i repl"}'
t deny:env-dump "$C" Bash '{"command":"x=1; env > /tmp/e.txt"}'
t deny:env-dump "$C" Bash '{"command":"sudo env -0"}'
t deny:env-dump "$C" Bash '{"command":"printenv"}'
t deny:env-dump "$C" Bash '{"command":"printenv | sort"}'
t deny:env-dump "$C" Bash '{"command":"set"}'
t deny:env-dump "$C" Bash '{"command":"set | less"}'
t deny:env-dump "$C" Bash '{"command":"export -p"}'
t deny:env-dump "$C" Bash '{"command":"declare -x"}'
t deny:env-dump "$C" Bash '{"command":"compgen -v"}'
t deny:env-dump "$C" Bash '{"command":"echo ${!REPL*}"}'
t deny:env-dump "$C" Bash '{"command":"cat /proc/self/environ"}'
t deny:env-dump "$C" Bash '{"command":"bash -lc \"env\""}'
t deny:env-dump "$C" Bash '{"command":"cmd /c set"}'
t deny:env-dump "$C" PowerShell '{"command":"Get-ChildItem Env:"}'
t deny:env-dump "$C" PowerShell '{"command":"gci env:* | Out-String"}'
t deny:env-dump "$C" PowerShell '{"command":"dir Env:\\"}'
t deny:env-dump "$C" PowerShell '{"command":"Get-ChildItem env:*TOKEN*"}'
t deny:env-dump "$C" PowerShell '{"command":"[Environment]::GetEnvironmentVariables()"}'
t deny:env-dump "$C" Bash '{"command":"cd /tmp\nenv"}'
t deny:env-dump "$C" Bash '{"command":"if true; then env; fi"}'
t deny:env-dump "$C" Bash '{"command":"/usr/bin/env"}'
t deny:env-dump "$C" Bash '{"command":"bash -c env"}'
t deny:env-dump "$C" Bash '{"command":"timeout 5 printenv"}'
t deny:env-dump "$C" Bash '{"command":"ps eww -p $$"}'
t deny:env-dump "$C" Bash '{"command":"python3 -c \"import os; print(os.environ)\""}'
t deny:env-dump "$C" Bash '{"command":"python3 -c \"import os; print(dict(os.environ.items()))\""}'
t deny:env-dump "$C" Bash '{"command":"node -p process.env"}'
t deny:env-dump "$C" PowerShell '{"command":"cmd /c set REPL"}'
# A session whose folder is inside the data folder.
t deny:data-cwd "$D/envs" Bash '{"command":"ls"}'
t deny:data-cwd "$D" Grep '{"pattern":"x"}'

# --- Denied in a TrendsMesh workspace that keeps keys in .secrets/ ----------------------------
# Naming the key store, by any reader (or none).
t deny:key-store "$W" Read '{"file_path":".secrets/api_keys.env"}'
t deny:key-store "$W" Read "{\"file_path\":\"$W/.secrets/api_keys.env\"}"
t deny:key-store "$W" Edit '{"file_path":".secrets/api_keys.env","old_string":"a","new_string":"b"}'
t deny:key-store "$W" Grep '{"pattern":"x","path":".secrets"}'
t deny:key-store "$W" Grep '{"pattern":"x","glob":"*.env"}'
t deny:key-store "$W" Bash '{"command":"cat .secrets/api_keys.env"}'
t deny:key-store "$W" Bash '{"command":"ls; od -c .secrets/token"}'
t deny:key-store "$W" Bash '{"command":"sh -c \"cat .secrets/api_keys.env\""}'
t deny:key-store "$W" Bash '{"command":"base64 .secrets/api_keys.env"}'
t deny:key-store "$W" Bash '{"command":"python3 -c \"print(open('"'"'.secrets/api_keys.env'"'"').read())\""}'
t deny:key-store "$W" Bash '{"command":"cat .s*/*"}'
t deny:key-store "$W" Bash '{"command":"cat .*/*"}'
t deny:key-store "$W" Bash '{"command":"find . -name \"*.env\" -exec cat {} +"}'
t deny:key-store "$W" Bash '{"command":"cat .env"}'
t deny:key-store "$W" PowerShell '{"command":"type .secrets\\api_keys.env"}'
t deny:key-store "$W" PowerShell '{"command":"(Get-Content .secrets/api_keys.env) | Out-String"}'
t deny:key-store "$W" Bash '{"command":"find . -name '"'"'api_keys*'"'"' -exec cat {} +"}'
# .secrets/ and api_keys.env are key stores from any folder.
t deny:key-store "$W/runs" Bash '{"command":"cat ../.secrets/api_keys.env"}'
t deny:key-store "$TMP" Bash '{"command":"cat ws/.secrets/api_keys.env"}'
t deny:key-store "$C" Read '{"file_path":"/w/.secrets/api_keys.env"}'
t deny:key-store "$C" Bash '{"command":"cat ~/api_keys.env"}'
t deny:key-store "$W/RUNS/01-refresh-ad" Bash '{"command":"cat ../../.secrets/api_keys.env"}'
# A search over the whole workspace (which holds .secrets/) for a provider or key word.
t deny:key-search "$W" Grep '{"pattern":"REPLICATE","path":"."}'
t deny:key-search "$W" Grep '{"pattern":"elevenlabs"}'
t deny:key-search "$W" Grep "{\"pattern\":\"api.?key\",\"path\":\"$W\"}"
t deny:key-search "$W" Bash '{"command":"grep -ri elevenlabs ."}'
t deny:key-search "$W" Bash '{"command":"grep -r elevenlabs . runs/"}'
t deny:key-search "$W" Bash '{"command":"rg -i token"}'
t deny:key-search "$W" PowerShell '{"command":"Get-ChildItem -Recurse | Select-String replicate"}'
t deny:key-search "$W" PowerShell '{"command":"findstr /s /i replicate *"}'
t deny:key-search "$W" Bash '{"command":"grep -r API ."}'
t deny:key-search "$W" Bash '{"command":"grep -r r8_ ."}'
t deny:key-search "$W" Bash '{"command":"grep -rI '"'"''"'"' ."}'
t deny:key-search "$W" Grep '{"pattern":".*"}'
t deny:key-search "$W/runs" Bash '{"command":"grep -r token .."}'
t deny:key-search "$TMP" Grep '{"pattern":"REPLICATE","path":"ws","output_mode":"content"}'

# --- Allowed: ordinary coding and the plugin's own development --------------------------------
t allow "$C" Bash '{"command":"grep -r token src/"}'
t allow "$C" Grep '{"pattern":"csrfToken","path":"src"}'
t allow "$C" Grep '{"pattern":"secret","path":"."}'
t allow "$C" Read '{"file_path":"/w/src/auth/token.ts"}'
t allow "$C" Bash '{"command":"ls src/auth/token","description":"List the secret token and api key handlers"}'
t allow "$C" Bash '{"command":"sed -n 1,20p src/settings.py"}'
t allow "$C" Bash '{"command":"awk -F, '"'"'{print $1}'"'"' data.csv"}'
t allow "$C" Bash '{"command":"cat .env"}'
t allow "$C" Read '{"file_path":"/w/.secrets.baseline"}'
t allow "$C" Edit '{"file_path":"/w/aws.ts","old_string":"a","new_string":"new AWS.SecretsManager()"}'
t allow "$C" Edit '{"file_path":"/w/vk.c","old_string":"a","new_string":"VK_FORMAT_R8_UNORM"}'
t allow "$C" Edit '{"file_path":"/w/tm/tools/__init__.py","old_string":"a","new_string":"ENV_VARS = {\"replicate_api_token\": \"REPLICATE_API_TOKEN\"}"}'
t allow "$C" Grep '{"pattern":"REPLICATE_API_TOKEN","path":"engine/src"}'
t allow "$C" Bash '{"command":"ls ~/.claude"}'
t allow "$C" Bash '{"command":"find . -name \"*.mp4\""}'
t allow "$C" Bash '{"command":"ls .claude/*"}'
t allow "$C" Bash '{"command":"cat .claude/settings*.json"}'
t allow "$C" Read '{"file_path":"/w/k8s/secrets.example.yaml"}'
t allow "$C" Bash '{"command":"sops -d secrets.enc.yaml"}'
t allow "$C" Bash '{"command":"echo \"env: production\" >> config.yml"}'
t allow "$C" Bash '{"command":"cat > .github/workflows/ci.yml <<'"'"'EOF'"'"'\njobs:\n  test:\n    env:\n      CI: true\nEOF"}'
t allow "$C" Bash '{"command":"grep -rn os.environ src"}'
t allow "$C" Bash '{"command":"ps -ef | grep python"}'
# The guard's own source can be read and searched (its name holds "secrets").
t allow "$C" Read "{\"file_path\":\"$P/bootstrap/guard-secrets.sh\"}"
t allow "$W" Read "{\"file_path\":\"$P/bootstrap/guard-secrets.ps1\"}"
t allow "$W" Bash "{\"command\":\"sed -n 1,40p '$P/bootstrap/guard-secrets.sh'\"}"
t allow "$W" Grep "{\"pattern\":\"deny\",\"path\":\"$P/bootstrap/guard-secrets.sh\"}"
t allow "$W" Glob "{\"pattern\":\"**/*{key,secret}*\",\"path\":\"$P\"}"
# Variables and environment commands that print no key.
t allow "$C" Bash '{"command":"env FOO=1 tm next --json"}'
t allow "$C" Bash '{"command":"env -u PYTHONPATH tm doctor --json"}'
t allow "$C" Bash '{"command":"set -euo pipefail; tm next --json"}'
t allow "$C" Bash '{"command":"export FOO=bar && echo \"$TM_PLUGIN_ROOT\""}'
t allow "$C" Bash '{"command":"printenv HOME"}'
t allow "$C" Bash '{"command":"docker run --env X=1 img"}'
t allow "$C" Bash '{"command":"tm brief --spec \"env\" --json"}'
t allow "$C" PowerShell '{"command":"$env:Path -split \";\""}'
t allow "$C" PowerShell '{"command":"Get-Item Env:Path"}'

# --- Allowed in a TrendsMesh workspace: the playbooks' own work (issue #6) ---------------------
for ws in "$W" "$W2"; do
  t allow "$ws" Read '{"file_path":"runs/01-refresh-ad/2026-11-05_ad3/manifest.md"}'
  t allow "$ws" Read '{"file_path":"runs/01-refresh-ad/2026-11-05_ad3/replicate_notes.txt"}'
  t allow "$ws" Bash '{"command":"tm next --run runs/01-refresh-ad/2026-11-05_ad3 --json"}'
  t allow "$ws" Bash '{"command":"tm tool replicate_run --run runs/x 03_wip/ai/frame1_v01.json --cost 0.1 --json"}'
  t allow "$ws" Bash '{"command":"tm doctor --outputs creative_brief --mcp trendsmesh=ok,meta=ok --json"}'
  t allow "$ws" Bash '{"command":"tm tool replicate_price --model google/veo-3 --json | head -20"}'
  t allow "$ws" Bash '{"command":"tm tool elevenlabs credits --run runs/x --json | head"}'
  t allow "$ws" Bash '{"command":"echo \"secret recipe ideas\" >> runs/02-creative-brief/x/search_log.txt"}'
  t allow "$ws" Bash '{"command":"cat runs/x/a.txt > runs/x/b.txt"}'
  t allow "$ws" Bash '{"command":"python3 -c \"import json; print(1)\" && cat runs/x/manifest.md | grep replicate"}'
  t allow "$ws" Bash '{"command":"tm record --run runs/x <<'"'"'EOF'"'"'\ntype: B-roll\nReplicate clip cost 0.10\nthe secret recipe, key features\nEOF"}'
  t allow "$ws" Bash '{"command":"cat > runs/x/notes.md <<'"'"'EOF'"'"'\nless is more: the secret of a keynote\nEOF"}'
  t allow "$ws" Bash '{"command":"less runs/x/replicate_notes.txt"}'
  t allow "$ws" Bash '{"command":"grep elevenlabs_plan runs/x/test.log"}'
  t allow "$ws" Bash '{"command":"grep -ri elevenlabs runs/x/test.log"}'
  t allow "$ws" Grep '{"pattern":"elevenlabs_plan","path":"runs/x/test.log"}'
  t allow "$ws" Grep '{"pattern":"secret recipe","path":"runs"}'
  t allow "$ws" Grep '{"pattern":"hook_rate"}'
  t allow "$ws" Glob '{"pattern":"**/*secret*"}'
  t allow "$ws" PowerShell '{"command":"Add-Content -Path runs\\x\\log.txt -Value \"secret recipe, key features\""}'
  t allow "$ws" PowerShell '{"command":"Select-String -Path runs\\x\\log.txt -Pattern \"secret recipe\""}'
  # Reader words inside arguments and quoted text are not commands (Polish "od", "more", "less").
  t allow "$ws" Bash '{"command":"tm tool elevenlabs tts --run runs/x --voice-id abc --text \"Zacznij od dziś\" --cost 300 --json"}'
  t allow "$ws" Bash '{"command":"tm tool elevenlabs tts --run runs/x --voice-id abc --text \"more or less\" --cost 300 --json"}'
  t allow "$ws" Bash '{"command":"tm tool elevenlabs history-search --run runs/x \"keynote mysteries security\" --json"}'
  t allow "$ws" Bash '{"command":"tm budget estimate ai_usd 2 --what \"Replicate Veo clip, more motion\""}'
  t allow "$ws" Bash '{"command":"tm budget estimate ai_usd 2 --what \"Replicate clip, type: B-roll\""}'
  # The programs the plugin installs in its data folder (guard-programs.txt) can be run.
  t allow "$ws" Bash '{"command":"\"$TM_PLUGIN_DATA/envs/abc/envs/default/bin/ffmpeg\" -i in.mp4 -f null -"}'
  t allow "$ws" Bash "{\"command\":\"'$D/envs/abc/envs/default/bin/ffprobe' -v error in.mp4\"}"
  t allow "$ws" Bash '{"command":"${TM_PLUGIN_DATA}/pixi/bin/pixi --version"}'
  t allow "$ws" Bash '{"command":"ls \"$TM_PLUGIN_DATA\"/envs/*/envs/default/bin/ffmpeg"}'
  t allow "$ws" PowerShell '{"command":"& \"$env:TM_PLUGIN_DATA\\envs\\abc\\envs\\default\\Library\\bin\\ffmpeg.exe\" -version"}'
  t allow "$ws" Bash '{"command":"\"$TM_PLUGIN_DATA/envs/abc/envs/base/bin/python\" -c \"print(1)\""}'
  t allow "$ws" Bash '{"command":"$TM_PLUGIN_DATA/envs/abc/envs/video/bin/node --version"}'
  t allow "$ws" Bash '{"command":"$TM_PLUGIN_DATA/envs/abc/envs/video/bin/npx remotion versions"}'
  t allow "$ws" Bash '{"command":"\"$TM_PLUGIN_DATA/remotion/node_modules/.remotion/chrome-headless-shell/linux64/chrome-headless-shell-linux64/chrome-headless-shell\" --version"}'
  t allow "$ws" PowerShell '{"command":"& \"$env:TM_PLUGIN_DATA\\envs\\abc\\envs\\base\\python.exe\" -V"}'
  t allow "$ws" PowerShell '{"command":"& \"$env:TM_PLUGIN_DATA\\envs\\abc\\envs\\video\\npx.cmd\" remotion versions"}'
  t allow "$ws" PowerShell '{"command":"& $env:TM_PLUGIN_DATA\\pixi\\bin\\pixi.exe --version"}'
  t allow "$ws" Read "{\"file_path\":\"$D/pixi/bin/pixi\"}"
  t allow "$ws" Bash "{\"command\":\"'$D/envs/abc/envs/base/bin/ffprobe' a.mp4 && '$D/envs/abc/envs/base/bin/ffmpeg' -i a.mp4 b.mp4\"}"
  t allow "$ws" Bash '{"command":"cd runs/x && \"$TM_PLUGIN_DATA/envs/abc/envs/default/bin/ffmpeg\" -i in.mp4 out.mp4"}'
  t allow "$ws" Bash '{"command":"\"$TM_PLUGIN_DATA/envs/abc/envs/default/bin/ffmpeg\" -i ../in.mp4 out.mp4"}'
  t allow "$ws" Bash '{"command":"tm next --json | jq '"'"'.[0]'"'"'"}'
  t allow "$ws" Bash '{"command":"jq '"'"'.items[] | .name'"'"' runs/x/a.json"}'
  t allow "$ws" Bash '{"command":"grep -ri keynote runs/02-creative-brief/"}'
done
# A workspace with no key store of its own can be searched as a whole.
t allow "$W2" Grep '{"pattern":"REPLICATE","path":"."}'
t allow "$W2" Bash '{"command":"grep -ri elevenlabs ."}'
# Ordinary commands the guard still blocks (issue #62): each block message says how to rephrase.
says "write that text to a file with the Write tool" "$W" Bash '{"command":"cat >> runs/x/notes.md <<'"'"'EOF'"'"'\nThe keys stay in .secrets/ and never in a run.\nEOF"}'
says "write that text to a file with the Write tool" "$W" Bash '{"command":"awk '"'"'/^title: .*/ {print}'"'"' runs/x/a.md"}'
says "write that text to a file with the Write tool" "$W" Bash '{"command":"python3 - <<'"'"'EOF'"'"'\nimport re\nprint(re.findall(r\"id: .*?;\", open(\"runs/x/a.md\").read()))\nEOF"}'
t deny:key-store "$W" Bash '{"command":"awk '"'"'/^title: .*/ {print}'"'"' runs/x/a.md"}'
t deny:data-parent "$C" Bash '{"command":"grep -rn \"width / 2\" ~/.claude/plugins/cache/tm/trendsmesh-playbooks/0.11.0/engine"}'
says "use the Grep tool with that folder as its path" "$C" Bash '{"command":"grep -rn \"width / 2\" ~/.claude/plugins/cache/tm/trendsmesh-playbooks/0.11.0/engine"}'
says "tm tool ffmpeg" "$C" Bash '{"command":"ls \"$TM_PLUGIN_DATA/envs\""}'
# The rephrased forms pass.
t allow "$W" Bash '{"command":"awk -f runs/x/titles.awk runs/x/a.md"}'
t allow "$W" Bash '{"command":"python3 runs/x/ids.py"}'
t allow "$C" Grep '{"pattern":"width / 2","path":"/Users/x/.claude/plugins/cache/tm/trendsmesh-playbooks/0.11.0/engine"}'
# Leaving the data folder is allowed.
t allow "$D/envs" Bash '{"command":"cd ~/project"}'

# Other tools and broken input pass (fail open).
t allow "$C" WebFetch '{"url":"https://example.com/secrets.env"}'
out=$(printf 'not json' | sh -c "$cmd") || fail "broken input: non-zero exit"
[ -z "$out" ] || fail "broken input printed: $out"

[ "$bad" -eq 0 ] || fail "$bad of $n calls failed ($RUNNERS)"
echo "guard-secrets tests passed: $n calls ($RUNNERS)"
