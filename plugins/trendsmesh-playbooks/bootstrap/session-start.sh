#!/bin/sh
# SessionStart hook (macOS, Linux). On Windows, where the hook may run in Git Bash, it hands over
# to session-start.ps1, which does the work there. Never prints a secret value.
case "$(uname -s 2>/dev/null)" in
  MINGW*|MSYS*|CYGWIN*)
    ps1="$(cd "$(dirname "$0")" && pwd)/session-start.ps1"
    command -v cygpath >/dev/null 2>&1 && ps1=$(cygpath -w "$ps1")
    exec powershell.exe -NoProfile -ExecutionPolicy Bypass -File "$ps1" ;;
esac

HERE=$(cd "$(dirname "$0")" && pwd)
ROOT=${CLAUDE_PLUGIN_ROOT:-$(dirname "$HERE")}
DATA=${CLAUDE_PLUGIN_DATA:-}
[ -n "$DATA" ] || exit 0
export CLAUDE_PLUGIN_DATA="$DATA"
mkdir -p "$DATA"

# 0. one line of context for every session (stdout is context for Claude)
echo "TrendsMesh playbooks: never search for, read or show the Replicate or ElevenLabs keys, not even masked; tm doctor says whether each is set."

PIXI="$DATA/pixi/bin/pixi"

# 1. paths.json (first, so that tm finds the plugin even when this hook is cut off during the
#    pixi download below), one key per line so bin/tm can read it without a JSON parser
json() { printf '%s' "$1" | sed 's/\\/\\\\/g; s/"/\\"/g'; }
mkdir -p "$HOME/.trendsmesh"
printf '{\n  "plugin_root": "%s",\n  "plugin_data": "%s",\n  "pixi": "%s"\n}\n' \
  "$(json "$ROOT")" "$(json "$DATA")" "$(json "$PIXI")" > "$HOME/.trendsmesh/paths.json"

# 2. make the folders visible to Bash tool calls
if [ -n "${CLAUDE_ENV_FILE:-}" ]; then
  q() { printf '%s' "$1" | sed "s/'/'\\\\''/g"; }
  printf "export TM_PLUGIN_ROOT='%s'\nexport TM_PLUGIN_DATA='%s'\n" "$(q "$ROOT")" "$(q "$DATA")" >> "$CLAUDE_ENV_FILE"
fi

# 3. pixi. What the installer prints goes to its log, never to stdout (stdout is context for
#    Claude); on a failure its one-line reason is kept and said at the end. tm tries again later.
pixi_ok=1
why=$(CLAUDE_PLUGIN_DATA="$DATA" sh "$HERE/install-pixi.sh" 2>&1 >/dev/null) || pixi_ok=

# 4. secrets.env, mode 0600 from the start
(
  umask 077
  rm -f "$DATA/secrets.env"
  : > "$DATA/secrets.env"
  for pair in REPLICATE_API_TOKEN:CLAUDE_PLUGIN_OPTION_REPLICATE_API_TOKEN \
              ELEVENLABS_API_KEY:CLAUDE_PLUGIN_OPTION_ELEVENLABS_API_KEY; do
    key=${pair%%:*}; var=${pair#*:}
    eval "val=\${$var:-}"
    case "$val" in
      *'
'*) val= ;;
    esac
    [ -n "$val" ] && printf '%s=%s\n' "$key" "$val" >> "$DATA/secrets.env"
  done
)
chmod 600 "$DATA/secrets.env"

if [ -z "$pixi_ok" ]; then
  why=$(printf '%s' "$why" | tr '\n' ' ' | tr -d '\000-\037\177')
  echo "TrendsMesh playbooks: its tools could not be set up, because pixi did not install into the plugin's data folder, so tm cannot run yet. The reason: ${why:-unknown}. Never install pixi yourself or change PATH or global packages. Running tm tries the install again; /trendsmesh-playbooks:doctor does that and tells the user the reason above in plain words."
  exit 0
fi

# 5. what is due: `tm due --quiet` prints one plain line per thing due (a measurement, a weekly trend report)
#    and nothing else.
#    A missing environment or a failure means "nothing due" (and prints nothing).
export PIXI_HOME="$DATA/pixi" PIXI_NO_PATH_UPDATE=1 TM_PLUGIN_ROOT="$ROOT" TM_PLUGIN_DATA="$DATA"
due=$("$PIXI" run --as-is --manifest-path "$ROOT/env/pixi.toml" -e base python -m tm due --quiet 2>/dev/null) || exit 0
[ -n "$due" ] && printf '%s\n' "$due"
exit 0
