#!/bin/sh
# PreToolUse hook (macOS, Linux, and Windows with Git Bash; guard-secrets.ps1 is the same check
# for Windows without Git Bash, rule for rule). Denies a tool call that would reach the API keys
# (Replicate, ElevenLabs): the files and folders they are kept in, the variables that hold them,
# or a dump of the whole environment. It checks what a call reads, not loose words in its text:
# a search phrase with "secret", a redirect, a pipe to head, a heredoc and the plugin's own tm
# commands all pass. It fails open: anything it cannot read is allowed, and it prints nothing
# when it allows a call. A denial names its rule and the part of the call that matched. It is a
# check of what a call asks for, so a deliberately disguised command (a path built from pieces)
# can still get past it; it catches the ordinary ways of reaching a key.
#
# Fields checked (tool_input): Read file_path; Grep path and glob (and its pattern for the key
# rules below); Glob path, pattern; Bash and PowerShell command (never description); Edit,
# MultiEdit, Write, NotebookEdit file_path / notebook_path; every field for the token shape.
# Commands are checked as written, without quotes and backslashes too (secr""ets.env), and a
# line break in a command counts as a ; (one command per line).
#
# Rules, in the order they are tried:
#   token          a Replicate token, r8_ and 30 or more letters and digits (never repeated);
#   data-cwd       the session's folder is inside the plugin data folder (only a cd passes);
#   secrets-file   secrets.env, the file the keys are kept in (also as secrets.e*,
#                  secrets*.env, or the Windows short name SECRET~1.ENV);
#   key-variable   REPLICATE_API_TOKEN or ELEVENLABS_API_KEY (also inside CLAUDE_PLUGIN_OPTION_...,
#                  and case-blind after $, env: or %), except in a Grep outside a workspace, so the
#                  plugin's own code can be searched;
#   env-dump       a dump of the whole environment: env, printenv, set, export -p, declare -x,
#                  compgen -v, ${!X*}, ps e, /proc/*/environ, os.environ or process.env in an
#                  interpreter, cmd's set PREFIX, Get-ChildItem Env:, GetEnvironmentVariables;
#   data-folder    the plugin data folder ($CLAUDE_PLUGIN_DATA expanded, CLAUDE_PLUGIN_DATA,
#                  TM_PLUGIN_DATA, plugins/data itself, plugins/data/<trendsmesh..., a glob or a
#                  short name such as TRENDS~1>,
#                  data/trendsmesh-playbooks...) other than as the full path of one of the
#                  programs the plugin installs there (ffmpeg, pixi...), which guard-programs.txt
#                  lists: the one list this guard, guard-secrets.ps1 and their tests read;
#   data-climb     a way out of one of those programs or into the data folder: .. or {..,} in
#                  the same path, cd/pushd/Set-Location to it, dirname, Split-Path, .parent,
#                  realpath...; when the path is put in a variable or a link (D=..., ln -s), any
#                  .. or cd;
#   data-parent    a recursive read (grep -r, rg, find, tar, cp -r, -Recurse, the Grep tool) of a
#                  folder above the data folder: /, home, ~/.claude, ~/.claude/plugins;
#   plugins-glob   a wildcard folder inside .claude/ or a wildcard in .claude/plugins/, which can
#                  reach the data folder;
#   key-store      .secrets/ or api_keys.env, from any folder (a workspace's own key store);
# and in a TrendsMesh workspace (the session's folder holds runs/0N-... or .secrets/, or is
# inside runs/):
#   key-store      also a .env file, a dot-name glob (.s*, .*) or api_keys*;
#   key-search     a recursive search, for replicate, elevenlabs, token, secret, api, key, r8_,
#                  sk_ or anything ('' or .*), of a folder that holds .secrets/ or a .env file (the
#                  Grep path, or the session's folder or its parent for a command that names no
#                  narrower path such as runs/). A Grep whose folder holds .secrets/ counts from
#                  any session folder.

HERE=$(cd "$(dirname "$0")" && pwd)
# A \n in a JSON string (a line break in a command) becomes " ; " before the fields are read.
fields=$(cat | awk '{ gsub(/\\\\/, "\003"); gsub(/\\n/, " ; "); print }' | awk -f "$HERE/json-fields.awk" 2>/dev/null) || exit 0
[ -n "$fields" ] || exit 0

get() {  # the values of the fields whose path matches the regex $1, one per line
  printf '%s\n' "$fields" | RE=$1 awk -F '\t' '$1 ~ ENVIRON["RE"] { sub(/^[^\t]*\t/, ""); print }'
}
slashes() { tr '\\' '/'; }
lower() { tr '[:upper:]' '[:lower:]'; }
# The first match of the ERE $2 in $1 (line by line), case-blind (mi) or exact (mc).
mi() { printf '%s\n' "$1" | grep -oiE -- "$2" 2>/dev/null | head -n 1; }
mc() { printf '%s\n' "$1" | grep -oE -- "$2" 2>/dev/null | head -n 1; }

tool=$(get '^tool_name$')
cwd=$(get '^cwd$' | slashes)
gpaths=
case "$tool" in
  Read) targets=$(get '^tool_input\.file_path$') ;;
  Grep) targets=$(get '^tool_input\.(path|pattern|glob)$'); gpaths=$(get '^tool_input\.(path|glob)$') ;;
  Glob) targets=$(get '^tool_input\.(path|pattern)$') ;;
  Bash|PowerShell) targets=$(get '^tool_input\.command$') ;;
  Edit|MultiEdit|Write|NotebookEdit) targets=$(get '^tool_input\.(file_path|notebook_path)$') ;;
  *) exit 0 ;;
esac
[ "$tool" = Grep ] || gpaths=$targets
all=$(get '^tool_input\.')
q="'"
# Three readings of the paths: as written (P), without quotes and backticks (Q: "$X"/a), and
# without backslashes too (N: secr\ets.env). P and Q have / for \.
P=$(printf '%s' "$gpaths" | slashes)
Q=$(printf '%s' "$P" | tr -d "\"$q\`")
N=$(printf '%s' "$gpaths" | tr -d "\\\\\"$q\`")
TN=$(printf '%s' "$targets" | tr -d "\\\\\"$q\`")
TP=$(printf '%s' "$targets" | slashes)
data=$(printf '%s' "${CLAUDE_PLUGIN_DATA:-}" | slashes)
dl=$(printf '%s' "$data" | lower); cl=$(printf '%s' "$cwd" | lower)
above=  # is the session's folder above the data folder?
[ -n "$dl" ] && [ -n "$cl" ] && case "$dl" in "$cl"/*) above=1 ;; esac

workspace=
case "$cl" in */runs/0[0-9]-*|*/runs) workspace=1 ;; esac
if [ -n "$cwd" ]; then
  [ -d "$cwd/.secrets" ] && workspace=1
  for d in "$cwd"/runs/0[0-9]-*; do [ -d "$d" ] && workspace=1; done
fi

rule= what= how= hit=
deny() { rule=$1; what=$2; how=$3; }

# Command position: the start, after ; & | ( { or a backtick, after sh -c or cmd /c, or after a
# word that runs the next one (sudo, xargs, exec, command, nohup, time, env, then, do, else, if,
# while, until, nice, stdbuf, !, timeout N). "od" or "set" inside an argument is no command.
AT="(^|[;&|({\`]|(^| )-[A-Za-z]*c +[\"$q]?|(^| )/[cCkK] +|(^|[^A-Za-z0-9_-])(sudo|xargs|exec|command|nohup|time|env|then|do|else|elif|if|while|until|nice|stdbuf|!|timeout +[^ ]+) ) *"
END=" *([;|&)}>\"$q]|\$)"

# token
if [ -n "$(mc "$all" 'r8_[A-Za-z0-9]{30,}')" ]; then
  deny token "this call holds a Replicate key (a token that starts with r8_)" \
    "Never write, pass or print a key: tm reads the keys itself."
fi
# data-cwd
if [ -z "$rule" ] && [ -n "$dl" ] && [ -n "$cl" ]; then
  case "$cl/" in
    "$dl"/*)
      case "$tool" in
        Bash|PowerShell)
          if [ -z "$(mi "$targets" '^ *cd( +[^;&|]*)? *$')" ] || [ -n "$(mi "$Q" '(^|[/ ])\.\.([/ ]|$)')" ]; then
            deny data-cwd "this session's folder is inside the plugin's data folder, where secrets.env (the keys) is kept" \
              "First cd back to the project folder; a plain cd is allowed."
          fi ;;
        Grep|Glob)
          deny data-cwd "this session's folder is inside the plugin's data folder, where secrets.env (the keys) is kept" \
            "First cd back to the project folder; a plain cd is allowed." ;;
      esac ;;
  esac
fi
# secrets-file
if [ -z "$rule" ]; then
  hit=$(mi "$P
$N" 'secrets\.(env|e[*?[]|[*?[])|secrets(\*|\[|\?[^ ;|&)])|ecrets\.env|secret~[0-9]')
  [ -n "$hit" ] && deny secrets-file "this call names secrets.env, the file that holds the keys" \
    "Don't open, search or copy it: tm reads it itself."
fi
# key-variable
if [ -z "$rule" ] && { [ "$tool" != Grep ] || [ -n "$workspace" ]; }; then
  hit=$(mc "$TN" 'REPLICATE_API_TOKEN|ELEVENLABS_API_KEY')
  [ -n "$hit" ] || hit=$(mi "$TN" '(env:|%|\$\{?)[A-Za-z_]*(replicate_api_token|elevenlabs_api_key)')
  [ -n "$hit" ] && deny key-variable "this call names a key variable (Replicate or ElevenLabs)" \
    "Don't print or test it: tm reads the keys itself."
fi
# env-dump
if [ -z "$rule" ]; then
  case "$tool" in Bash|PowerShell)
    re="${AT}([^ ;|&(]*/)?(env|printenv)( +-[A-Za-z0-9-]*)*${END}|${AT}set${END}|${AT}(export|declare|typeset)( +-[pxg]+)*${END}"
    re="$re|${AT}compgen +-[ve]|${AT}ps +[a-z]*e[a-z]*( |\$)|/[ck] +set +[a-z0-9_]+${END}"
    re="$re|\\\$\\{![A-Za-z_][A-Za-z0-9_]*[*@]\\}|/proc/[^/ ]*/environ|GetEnvironmentVariables"
    re="$re|(python[0-9.]*|node|perl|ruby|deno|bun|php) [^|&]*(os\\.environ(\$|[^.[a-z_]|\\.(items|copy|keys|values))|process\\.env(\$|[^.[a-z_])|%env)"
    re="$re|(^|[^\$A-Za-z0-9_:])env:/?( *([|)]|\$)|\\*|[A-Za-z0-9_]*[*?[])"
    hit=$(mi "$TP
$TN" "$re")
    [ -n "$hit" ] && deny env-dump "this command prints the whole environment, which can hold the keys" \
      "Print only the variable you need, by name (for example echo \"\$TM_PLUGIN_ROOT\")." ;;
  esac
fi
# data-folder, data-climb and data-parent. Each mention of the data folder is looked at in turn:
# one followed by the rest of a program's path from guard-programs.txt is that program (and
# becomes @), any other is the folder itself. Each word that is a folder above the data folder
# is noted too.
if [ -z "$rule" ]; then
  refs=$(printf '%s\n' "$Q" | LIT=$dl CWDL=$cl LIST="$HERE/guard-programs.txt" awk '
    BEGIN {
      lit = ENVIRON["LIT"]; cwdl = ENVIRON["CWDL"]; soh = sprintf("%c", 1)
      re = "(\\$\\{?(env:)?|%)?(claude|tm)_plugin_data[}%]?|plugins/data/[^/ ;|&)]*(trendsmesh|[*?[~])[^/ ;|&)]*"
      re = re "|plugins/data/?([ ;|&)]|$)|(^|[^a-z0-9_.-])data/trendsmesh-playbooks[^/ ;|&)]*|" soh
      # The programs, as one regex: a * is one name (no leading dot), anything else as it is.
      progs = ""
      while ((getline line < ENVIRON["LIST"]) > 0) {
        sub(/\r$/, "", line); sub(/^[ \t]+/, "", line); sub(/[ \t]+$/, "", line)
        if (line == "" || line ~ /^#/ || line ~ /^outside:/) continue
        line = tolower(line); p = ""
        for (k = 1; k <= length(line); k++) {
          ch = substr(line, k, 1)
          if (ch == "*") p = p "[a-z0-9_*+-][a-z0-9_.*+-]*"
          else if (ch ~ /[a-z0-9_\/-]/) p = p ch
          else p = p "[" ch "]"
        }
        progs = progs (progs == "" ? "" : "|") p
      }
      prog = progs == "" ? "" : "^/(" progs ")([ ;|&)<>]|$)"
    }
    {
      n = split(tolower($0), tk, /[ ;|&()]+/)
      for (k = 1; k <= n; k++) {
        t = tk[k]; if (t != "/") sub(/\/+$/, "", t)
        if (t == "") continue
        if (t == "/" || t ~ /^(~|\$home|\$\{home\}|%userprofile%|\$env:userprofile)$/ || t ~ /(^|\/)\.claude(\/plugins)?$/ \
            || (lit != "" && t ~ /^(\/|[a-z]:\/)/ && index(lit, t "/") == 1) \
            || (lit != "" && cwdl != "" && (t == "." || t == "*" || t == "./*") && index(lit, cwdl "/") == 1))
          print "parent\t" t
      }
      s = $0; l = tolower(s)
      if (lit != "") {  # the expanded folder, as a literal: marked with \001 in both copies
        while ((i = index(l, lit)) > 0) {
          l = substr(l, 1, i - 1) soh substr(l, i + length(lit))
          s = substr(s, 1, i - 1) soh substr(s, i + length(lit))
        }
      }
      while (match(l, re)) {
        any = 1
        ref = substr(s, RSTART, RLENGTH); rest = substr(l, RSTART + RLENGTH); at = RSTART; n = RLENGTH
        if (prog != "" && match(rest, prog)) {
          len = RLENGTH; if (substr(rest, len, 1) ~ /[ ;|&)<>]/) len--
          cut = at + n + len; RSTART = at
          l = substr(l, 1, RSTART - 1) "@" substr(l, cut)
          s = substr(s, 1, RSTART - 1) "@" substr(s, cut)
          continue
        }
        if (index(ref, soh)) ref = "the data folder'"'"'s path"
        sub(/^[^$%a-zA-Z0-9.]/, "", ref)
        print "deny\t" ref; exit
      }
      print "s\t" l
    }
    END { if (any) print "any" }')
  field() { printf '%s\n' "$refs" | awk -F '\t' -v k="$1" '$1 == k { sub(/^[^\t]*\t/, ""); print }'; }
  bad=$(field deny | head -n 1)
  if [ -n "$bad" ]; then
    hit=$bad
    deny data-folder "this call names the plugin's data folder, where secrets.env (the keys) is kept, other than as the full path of a program the plugin installed there" \
      "Use the tm command the playbook gives (tm tool ffmpeg, for example). Only the programs in the plugin's bootstrap/guard-programs.txt (pixi, the environments' python, ffmpeg, ffprobe, node, npm and npx) can be named, by their full path with nothing after it, for example \"\$TM_PLUGIN_DATA/envs/<folder>/envs/base/bin/ffmpeg\"."
  elif printf '%s\n' "$refs" | grep -qx any; then
    S=$(field s)
    re='@[^ ;|&)]*[/{,]\.\.([/ ;|&),}]|$)|(cd|pushd|chdir|set-location|push-location|sl) +@|dirname|split-path|\.parent|-parent|pardir|realpath|readlink|\$\{[a-z_][a-z0-9_]*%'
    if [ -n "$(mi "$S" '[a-z_][a-z0-9_:]* *= *@|(^|[^a-z0-9_-])(ln|mklink|new-item)( |$)|symboliclink|junction')" ]; then
      re="$re|(^|[/ {,])\\.\\.([/ ;|&),}]|\$)|(^|[^a-z0-9_-])(cd|pushd|chdir|set-location|push-location|sl)( |\$)"
    fi
    hit=$(mi "$S" "$re")
    [ -n "$hit" ] && deny data-climb "this call names a program in the plugin's data folder and climbs out of it, or moves into the folder" \
      "Run the program by its full path, without cd, .. or a parent-folder lookup."
  fi
  if [ -z "$rule" ]; then
    hit=$(field parent | head -n 1)
    [ -z "$hit" ] && [ "$tool" = Grep ] && [ -n "$above" ] && [ -z "$(get '^tool_input\.path$')" ] && hit="the session's folder"
    if [ -n "$hit" ]; then
      case "$tool" in
        Grep) ;;
        Bash|PowerShell)
          rec="${AT}(rg|ag|ack|find|tar|zip|rsync|7z)( |\$)|(grep|egrep|fgrep)( [^|;&]*)? -[a-z]*r|(grep|egrep|fgrep) [^|;&]*--recursive"
          rec="$rec|(^|[^a-z0-9_-])cp( [^|;&]*)? -[a-z]*[ra]|-recurse|robocopy|xcopy|compress-archive|findstr [^|;&]*/s"
          [ -n "$(mi "$TP" "$rec")" ] || hit= ;;
        *) hit= ;;
      esac
      [ -n "$hit" ] && deny data-parent "this call reads all of a folder that holds the plugin's data folder (/, home, ~/.claude or ~/.claude/plugins), where secrets.env (the keys) is kept" \
        "Search or copy a narrower folder, one outside ~/.claude/plugins/data (for the plugin's own code, its folder: \$TM_PLUGIN_ROOT). When the match is only text in the command (a / or ~ in a pattern), use the Grep tool with that folder as its path, or put the pattern in a file (grep -f)."
    fi
  fi
fi
# plugins-glob
if [ -z "$rule" ]; then
  hit=$(mi "$Q" '\.claude/([^/ ]*[*?[][^/ ]*/|plugins/[^/ ]*[*?[])')
  [ -n "$hit" ] && deny plugins-glob "this call uses a wildcard inside .claude, which can reach the plugin's data folder where the keys are kept" \
    "Name the folder exactly, without * or ?."
fi
# key-store and key-search
store_at() {  # does folder $1 hold .secrets/ or a .env file?
  [ -e "$1/.secrets" ] || [ -e "$1/.env" ] && return 0
  for f in "$1"/*.env; do [ -e "$f" ] && return 0; break; done
  return 1
}
if [ -z "$rule" ] && [ "$tool" != Glob ]; then
  hit=$(mi "$Q" '(^|[/ =(])\.secrets(/|[ ;|&)]|$)|api_keys\.env')
  [ -n "$hit" ] || [ -z "$workspace" ] ||
    hit=$(mi "$Q" '(^|[/ =(])[^/ =(]*\.env([ ;|&)]|$)|(^|[/ =(])\.env\.[a-z0-9_-]+|(^|[/ =(])\.[^/ .]*[*?]|api_keys')
  [ -n "$hit" ] && deny key-store "this call names a key store (.secrets/, api_keys.env or a workspace's .env file)" \
    "Don't open, search or copy it: tm reads the keys itself. When it is only text in the command (a note in a heredoc, or a regex such as .* or .*?), write that text to a file with the Write tool and use the file (awk -f, python3 script.py, a note appended from it)."
fi
if [ -z "$rule" ] && { [ -n "$workspace" ] || [ "$tool" = Grep ]; }; then
  hit=
  words="replicate|elevenlabs|token|secret|api|key|r8_|sk_|(^| )(''|\"\")( |\$)"
  case "$tool" in
    Grep)
      root=$(get '^tool_input\.path$' | slashes)
      case "$root" in "") root=$cwd ;; /*|[A-Za-z]:/*) ;; *) root="$cwd/$root" ;; esac
      if [ -e "$root/.secrets" ] || { [ -n "$workspace" ] && store_at "$root"; }; then
        pat=$(get '^tool_input\.pattern$')
        hit=$(mi "$pat" "$words")
        [ -n "$hit" ] || [ -z "$(mi "$pat" '^[.^$*+?()|= -]*$')" ] || hit=$pat
      fi ;;
    Bash|PowerShell)
      if [ -n "$workspace" ] && [ -n "$cwd" ] && { store_at "$cwd" || store_at "$cwd/.."; }; then
        rec="${AT}(rg|ag|ack|find)( |\$)|${AT}(grep|egrep|fgrep)( [^|;&]*)? -[a-z]*r|${AT}(grep|egrep|fgrep) [^|;&]*--recursive"
        rec="$rec|findstr [^|;&]*/s|(get-childitem|gci|dir|ls) [^|;&]*-r[^|;&]*\\| *(select-string|sls)"
        narrow='(rg|ag|ack|find|grep|egrep|fgrep|findstr|select-string|sls|get-childitem|gci|dir|ls)( [^|;&>]*)? [a-z0-9_][^ |;&)>]*/'
        rootish='(^| )(\.|\./|\.\.|\.\./|\*|\.\*|\./\*|\*/)( |[;|&)]|$)'
        if [ -n "$(mi "$TP" "$rec")" ] && { [ -z "$(mi "$Q" "$narrow")" ] || [ -n "$(mi "$Q" "$rootish")" ]; }; then
          hit=$(mi "$TP" "$words")
        fi
      fi ;;
  esac
  [ -n "$hit" ] && deny key-search "this search covers a folder that holds the workspace's key store (.secrets/ or a .env file) and looks for a key word" \
    "Search a narrower path such as runs/ (the Grep tool's path, or a path in the command), or one file."
fi
[ -n "$rule" ] || exit 0

esc() { printf '%s' "$1" | tr -d '\000-\037' | sed 's/\\/\\\\/g; s/"/\\"/g'; }
hit=$(printf '%s' "$hit" | sed "s/^[ ;&|({\`\"$q=]*//; s/[ ;&|)}>\"$q]*\$//")
said=
[ -n "$hit" ] && [ "$rule" != token ] && said=" It matched: $hit."
reason="Blocked by the TrendsMesh playbooks plugin's key guard (rule: $rule): $what.$said $how Keys are never shown, not even masked: tm doctor says whether each key is set, and the user changes them in /plugin, under Installed, trendsmesh-playbooks, Configure options."
printf '{"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "deny", "permissionDecisionReason": "%s"}}\n' "$(esc "$reason")"
exit 0
