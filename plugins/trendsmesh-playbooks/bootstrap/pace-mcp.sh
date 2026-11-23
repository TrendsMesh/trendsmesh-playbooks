#!/bin/sh
# PreToolUse hook for the TrendsMesh tools (macOS, Linux, and Windows with Git Bash; pace-mcp.ps1 is the same
# for Windows without Git Bash): the pacer of issue #129. Each call waits until it fits TrendsMesh's limits
# (10 calls a second, 10 searches and 20 video pages a minute, or the ones the latest saved get_usage answer
# gives), so none is refused with rate_limited. A call that could not go within 65 s is denied with what to
# do. The rule is tm.trend_pace's (read its header); pace.awk decides, this script finds the workspace, holds
# the lock and sleeps. No Python runs here (the owner's #148 line 12): five short processes a call, where tm
# costs about 0.5-1.5 s. Without a clock in milliseconds (no GNU date, no perl), it hands over to tm trends pace.
#
# The call log is <workspace>/.trendsmesh/pace.jsonl, the workspace being the event's cwd or the nearest folder
# above it holding .trendsmesh/ or runs/0N-..., never the home folder or above it; else the cwd. The lock is the
# file .trendsmesh/pace.lock holding the time it was taken (tm trends pace takes the same one), made by the
# shell's own noclobber redirection, an exclusive create: Claude Code runs the hooks of parallel calls at the
# same time. Never mkdir's exit status: Ubuntu 26.04's mkdir (uutils coreutils) exits 0 when another call made
# the folder first. An older version's lock is the folder pace.lock with the time in pace.lock/t, and it is
# waited for the same way. EVAL_TM_PACE=off (a claude plugin eval case's env:, mocks have no limits) turns it
# off. It never fails a call: anything unexpected lets it go.
[ "${EVAL_TM_PACE:-}" != off ] || exit 0
case $0 in */*) HERE=${0%/*} ;; *) HERE=. ;; esac
ROOT=${HERE%/*}
# The event's tool and cwd in one pass (the first string value of each key, unescaped; a key inside the input's
# text is escaped, so only the event's own match), the tool's short name, the cwd with forward slashes.
fields=$(awk '
  function grab(k,   re, s) {
    re = "\"" k "\"[ \t]*:[ \t]*\"([^\"\\\\]|\\\\.)*\""
    if (!match(all, re)) return ""
    s = substr(all, RSTART, RLENGTH); sub(/^"[^"]*"[ \t]*:[ \t]*"/, "", s); s = substr(s, 1, length(s) - 1)
    gsub(/\\"/, "\"", s); gsub(/\\\\/, "\\", s); return s
  }
  { all = all $0 "\n" }
  END { t = grab("tool_name"); sub(/.*__/, "", t); c = grab("cwd"); gsub(/\\/, "/", c); print t; print c }')
tool=${fields%%
*}
cwd=${fields#*
}
case $tool in ''|*[!A-Za-z0-9_-]*) tool=other ;; esac
[ -n "$cwd" ] && [ "$cwd" != "$fields" ] || exit 0
clock=date
case ${OSTYPE:-} in darwin*) clock=perl ;; esac            # macOS's date has no milliseconds
stamp() {  # now = epoch ms, from date's nanoseconds (Linux, Git Bash) or perl (macOS)
  if [ "$clock" = date ]; then
    # %s%N, never %3N: Ubuntu 26.04's date (uutils coreutils) drops %3N's leading zeros (.025 s gives 253)
    now=$(date +%s%N 2>/dev/null)
    case $now in ''|*[!0-9]*) clock=perl ;; *)
      if [ ${#now} -ge 16 ]; then now=${now%??????}; return 0; fi
      clock=perl ;;
    esac
  fi
  now=$(perl -MTime::HiRes=time -e 'printf "%d", time() * 1000' 2>/dev/null)
  case $now in ''|*[!0-9]*) return 1 ;; esac
}
dir=${cwd%/}
[ -n "$dir" ] || dir=/
home=${HOME%/}
ws=
d=$dir
while [ -n "$d" ] && [ "$d" != "$home" ]; do
  if [ -d "$d/.trendsmesh" ]; then ws=$d; break; fi
  for r in "$d"/runs/0[0-9]-*; do
    if [ -d "$r" ]; then ws=$d; break; fi
  done
  [ -z "$ws" ] || break
  up=${d%/*}
  [ "$up" != "$d" ] || break
  d=$up
done
[ -n "$ws" ] || ws=$dir
at="$ws/.trendsmesh"
[ -d "$at" ] || mkdir -p "$at" 2>/dev/null || exit 0
lock="$at/pace.lock"
tries=0
while ! (set -C; : > "$lock") 2>/dev/null; do
  # a lock is held for milliseconds: one older than 5 s, or one still there after 250 tries, was left by a killed hook
  held=
  if [ -d "$lock" ]; then { read -r held < "$lock/t"; } 2>/dev/null; else { read -r held < "$lock"; } 2>/dev/null; fi
  case $held in ''|*[!0-9]*) held= ;; esac
  if [ -n "$held" ] && stamp && [ $((now - held)) -gt 5000 ] || [ "$tries" -ge 250 ]; then
    rm -rf "$lock" 2>/dev/null
    tries=0
    continue
  fi
  tries=$((tries + 1))
  sleep 0.02
done
trap 'rm -rf "$lock" 2>/dev/null' EXIT INT TERM HUP
if ! stamp; then                                           # no clock in milliseconds: tm paces it instead
  rm -rf "$lock" 2>/dev/null
  trap - EXIT INT TERM HUP
  export TM_PLUGIN_ROOT="$ROOT"
  [ -z "${CLAUDE_PLUGIN_DATA:-}" ] || export TM_PLUGIN_DATA="$CLAUDE_PLUGIN_DATA"
  esc=$(printf '%s' "$cwd" | sed 's/\\/\\\\/g; s/"/\\"/g')
  printf '{"cwd": "%s", "tool_name": "%s"}' "$esc" "$tool" | sh "$ROOT/bin/tm" trends pace 2>/dev/null
  exit 0
fi
printf '%s' "$now" > "$lock"
lim="$at/pace-limits.tsv"
[ -f "$lim" ] || lim=/dev/null
log="$at/pace.jsonl"
[ -f "$log" ] || : > "$log"
# pace.awk reads the whole log, then writes it again (the calls still needed, and this one's booked moment)
out=$(awk -v now="$now" -v tool="$tool" -v margin=300 -v maxwait=65000 -v lim="$lim" -v out="$log" \
  -f "$HERE/pace.awk" "$lim" "$log" 2>/dev/null)
rm -rf "$lock" 2>/dev/null
trap - EXIT INT TERM HUP
case $out in
  "go "*)
    wait=${out#go }
    case $wait in 0.000|'') ;; *) sleep "$wait" ;; esac
    ;;
  "deny "*)
    reason=$(printf '%s' "${out#deny }" | sed 's/\\/\\\\/g; s/"/\\"/g')
    printf '{"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "deny", "permissionDecisionReason": "%s"}}\n' "$reason"
    ;;
esac
exit 0
