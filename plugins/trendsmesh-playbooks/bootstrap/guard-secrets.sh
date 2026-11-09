#!/bin/sh
# PreToolUse hook (macOS, Linux, and Windows with Git Bash; guard-secrets.ps1 is the same check
# for Windows without Git Bash). Denies a tool call that would read or search for the API keys
# (Replicate, ElevenLabs). It checks what a call asks for, not what it returns. It fails open:
# anything it cannot read is allowed, and it prints nothing when it allows a call.
#
# Fields checked (tool_input): Read file_path; Grep path, pattern, glob; Glob path, pattern;
# Bash and PowerShell command (never description); Edit, MultiEdit, Write, NotebookEdit
# file_path / notebook_path, and their content for the token shape only.
#
# Denied when a checked field holds:
#   - the plugin data folder: $CLAUDE_PLUGIN_DATA expanded, the names CLAUDE_PLUGIN_DATA or
#     TM_PLUGIN_DATA, or a path under .claude/plugins/data/ for this plugin (or a glob there);
#   - secrets.env (in paths and commands);
#   - the exact names REPLICATE_API_TOKEN or ELEVENLABS_API_KEY (also inside
#     CLAUDE_PLUGIN_OPTION_...), except in Grep and in file contents outside a TrendsMesh
#     workspace, so the plugin's own code can be searched and edited;
#   - a Replicate token, r8_ followed by 30 or more letters and digits (any field);
#   - in a TrendsMesh workspace only (the session's folder holds runs/01-refresh-ad/): a read or
#     search naming replicate, elevenlabs, token, secret or api key. A Bash or PowerShell command
#     is a read only when a reader (cat, grep, less, od, type, Get-Content...) stands in command
#     position, never because an argument such as an ad's line holds the word.

HERE=$(cd "$(dirname "$0")" && pwd)
fields=$(cat | awk -f "$HERE/json-fields.awk" 2>/dev/null) || exit 0
[ -n "$fields" ] || exit 0

get() {  # the values of the fields whose path matches the regex $1, one per line
  printf '%s\n' "$fields" | awk -F '\t' -v re="$1" '$1 ~ re { sub(/^[^\t]*\t/, ""); print }'
}
slashes() { tr '\\' '/'; }

tool=$(get '^tool_name$')
cwd=$(get '^cwd$' | slashes)
case "$tool" in
  Read) targets=$(get '^tool_input\.file_path$') ;;
  Grep) targets=$(get '^tool_input\.(path|pattern|glob)$') ;;
  Glob) targets=$(get '^tool_input\.(path|pattern)$') ;;
  Bash|PowerShell) targets=$(get '^tool_input\.command$') ;;
  Edit|MultiEdit|Write|NotebookEdit) targets=$(get '^tool_input\.(file_path|notebook_path)$') ;;
  *) exit 0 ;;
esac
all=$(get '^tool_input\.')
paths=$(printf '%s' "$targets" | slashes)

workspace=
case "$cwd" in
  */runs/01-refresh-ad|*/runs/01-refresh-ad/*) workspace=1 ;;
esac
[ -n "$cwd" ] && [ -d "$cwd/runs/01-refresh-ad" ] && workspace=1

deny=
has() { printf '%s' "$1" | grep -qE -- "$2"; }
hasF() { printf '%s' "$1" | grep -qF -- "$2"; }

# The plugin data folder.
data=$(printf '%s' "${CLAUDE_PLUGIN_DATA:-}" | slashes)
if [ -n "$data" ] && hasF "$paths" "$data"; then deny=1; fi
if has "$paths" 'CLAUDE_PLUGIN_DATA|TM_PLUGIN_DATA'; then deny=1; fi
if has "$paths" '\.claude/plugins/data/([^/ "]*trendsmesh|[^/ "]*[*?[])'; then deny=1; fi
# secrets.env, in paths and commands (a Grep pattern is not a path).
case "$tool" in
  Grep) gpaths=$(get '^tool_input\.(path|glob)$' | slashes) ;;
  *) gpaths=$paths ;;
esac
if hasF "$gpaths" 'secrets.env'; then deny=1; fi
# The key names, exactly.
names='REPLICATE_API_TOKEN|ELEVENLABS_API_KEY'
case "$tool" in
  Grep) [ -n "$workspace" ] && has "$targets" "$names" && deny=1 ;;
  *) has "$targets" "$names" && deny=1 ;;
esac
# A Replicate token, in any field.
if has "$all" 'r8_[A-Za-z0-9]{30,}'; then deny=1; fi
# In a TrendsMesh workspace: reads and searches that name a key.
if [ -n "$workspace" ] && [ -z "$deny" ]; then
  words='[Rr][Ee][Pp][Ll][Ii][Cc][Aa][Tt][Ee]|[Ee][Ll][Ee][Vv][Ee][Nn][Ll][Aa][Bb][Ss]|[Tt][Oo][Kk][Ee][Nn]|[Ss][Ee][Cc][Rr][Ee][Tt]|[Aa][Pp][Ii][ _-]?[Kk][Ee][Yy]'
  case "$tool" in
    Read|Grep|Glob) has "$targets" "$words" && deny=1 ;;
    Bash|PowerShell)
      # A reader counts only in command position: at the start of a line, after ; | & ( $( or a
      # backtick, after sh -c "..." and its kin, or after sudo, xargs, exec, command, env, nohup
      # or time. So "od", "more", "less" or "type" inside an argument (an ad's line) is no reader.
      at='(^|[;&|(`]|-[A-Za-z]*c[[:space:]]+["'"'"']|(^|[^A-Za-z0-9_-])(sudo|xargs|exec|command|env|nohup|time)[[:space:]])[[:space:]]*'
      verbs="${at}(grep|egrep|fgrep|rg|ag|ack|awk|sed|cat|head|tail|less|more|strings|xxd|od|findstr|Select-String|Get-Content|gc|type)([^A-Za-z0-9_-]|\$)"
      has "$targets" "$verbs" && has "$targets" "$words" && deny=1 ;;
  esac
fi
[ -n "$deny" ] || exit 0

printf '%s\n' '{"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "deny", "permissionDecisionReason": "Blocked by the TrendsMesh playbooks plugin: this call would read or search for a Replicate or ElevenLabs key, or look inside the plugin'"'"'s data folder where they are kept. Keys are never shown, not even masked. To check a key, run tm doctor (it says whether each key is set); the user sees and changes it in /plugin, trendsmesh-playbooks, configure. If this call has nothing to do with keys, rephrase it so it does not name a key file, a key variable or that folder."}}'
exit 0
