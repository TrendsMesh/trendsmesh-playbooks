#!/bin/sh
# PostToolUse hook for the TrendsMesh tools, the Ad Library search, and a creative brief's Meta reads
# and artifacts answers (macOS, Linux, and Windows with Git Bash; collect-mcp.ps1 is the same for
# Windows without Git Bash). While a trend research or creative brief run collects (`tm trends
# collect on` wrote <workspace>/.trendsmesh/collect.json), it hands the event to `tm trends spool`,
# which saves the answer into the run and prints the summary Claude sees instead of a search, a list
# or a video page. hooks.json's matcher picks the tools; this script has no filter of its own. It
# always exits 0.
#
# The workspace comes from the event's `cwd` on stdin (paths.json knows the plugin, not the
# workspace): that folder, or the nearest one above it holding the marker, as Claude may have gone
# into a run folder. With no marker, or a marker claimed by another session (`session` in it is not
# this event's `session_id`), it exits at once, without starting Python. Values are read with awk's
# leftmost match, not json-fields.awk, which takes half a second on a 400 KB search answer; a key
# inside the answer's text is escaped (\"cwd\"), so only the event's own keys match.
#
# When tm itself fails (spool always exits 0, so the engine never ran), it prints one fixed line
# telling Claude the answer was not saved, and adds a line to the run's 02_research/collect_failures.log.
HERE=$(cd "$(dirname "$0")" && pwd)
ROOT=$(dirname "$HERE")
value() {  # the first string value of key $1 in the JSON on stdin, unescaped
  awk -v k="$1" 'BEGIN { re = "\"" k "\"[ \t]*:[ \t]*\"([^\"\\\\]|\\\\.)*\"" }
    match($0, re) { s = substr($0, RSTART, RLENGTH); sub(/^"[^"]*"[ \t]*:[ \t]*"/, "", s)
                    print substr(s, 1, length(s) - 1); exit }' | sed 's/\\"/"/g; s/\\\\/\\/g'
}
event=$(cat)
cwd=$(printf '%s\n' "$event" | value cwd | tr '\\' '/')
[ -n "$cwd" ] || exit 0
dir=${cwd%/}
while [ ! -f "$dir/.trendsmesh/collect.json" ]; do
  up=${dir%/*}
  if [ -z "$up" ] || [ "$up" = "$dir" ]; then exit 0; fi
  dir=$up
done
marker="$dir/.trendsmesh/collect.json"
owner=$(value session < "$marker")
if [ -n "$owner" ] && [ "$owner" != "$(printf '%s\n' "$event" | value session_id)" ]; then exit 0; fi

# bin/tm finds the plugin from these (else from ~/.trendsmesh/paths.json): this plugin's own root,
# so the engine and the hook come from the same version.
export TM_PLUGIN_ROOT="$ROOT"
[ -z "${CLAUDE_PLUGIN_DATA:-}" ] || export TM_PLUGIN_DATA="$CLAUDE_PLUGIN_DATA"
# Under `claude plugin eval` the plugin's data folder has no pixi, so bin/tm cannot start: an eval case
# sets EVAL_TM_SOURCE_ENGINE=1 (in its prompt.md front-matter `env:`, which takes EVAL_* keys only) and
# the hook runs this plugin's own engine source with python3 (3.11 or newer, with PyYAML; -P keeps the
# working directory off the import path). Nothing from the workspace is run, with or without it.
if [ "${EVAL_TM_SOURCE_ENGINE:-}" = 1 ]; then
  out=$(printf '%s' "$event" | PYTHONPATH="$ROOT/engine/src" PYTHONDONTWRITEBYTECODE=1 python3 -P -m tm trends spool 2>/dev/null)
else
  out=$(printf '%s' "$event" | sh "$ROOT/bin/tm" trends spool 2>/dev/null)
fi
rc=$?
if [ "$rc" -eq 0 ]; then
  [ -z "$out" ] || printf '%s\n' "$out"
  exit 0
fi
run=$(value run < "$marker")
tool=$(printf '%s\n' "$event" | value tool_name)
if [ -n "$run" ] && [ -d "$dir/$run/02_research" ]; then
  printf '%s\t%s\tthe engine did not start (tm exited %s)\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "${tool##*__}" "$rc" \
    >> "$dir/$run/02_research/collect_failures.log" 2>/dev/null
fi
printf '%s\n' '{"hookSpecificOutput": {"hookEventName": "PostToolUse", "additionalContext": "This answer was not saved to the run (the plugin'"'"'s engine did not start). Save it with tm trends ingest --run <run folder> --tool <tool name> --input <file with the tool'"'"'s input> --file <file with this answer>; tm doctor says why the engine did not start. The run continues from the same place."}}'
exit 0
