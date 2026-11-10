#!/bin/sh
# Installs pixi into <data>/pixi if missing, and points its environments at <data>/envs.
# PIXI_NO_PATH_UPDATE keeps the user's shell profile untouched. PIXI_VERSION pins the pixi that
# CI and the lock file were made with: another pixi may read the lock and --frozen differently
# (keep it equal to pixi-version in .github/workflows/ci.yml and install-pixi.ps1).
# Everything the download and the installer print goes to <data>/install-pixi.log (removed again
# when pixi installs). When pixi is not there afterwards it exits non-zero and prints one line on
# stderr: what failed, what the installer said last, and where the log is.
set -eu
DATA=${CLAUDE_PLUGIN_DATA:?CLAUDE_PLUGIN_DATA is not set}
PIXI_HOME="$DATA/pixi"
PIXI_VERSION=v0.84.1
LOG="$DATA/install-pixi.log"
mkdir -p "$PIXI_HOME"

SITES="pixi.sh, pixi.prefix.dev, github.com and release-assets.githubusercontent.com"
WAIT=${TM_TEST_PIXI_WAIT:-75}   # seconds for the installer; with the 30 s download that stays inside the hook's 120 s

# The last line the download or the installer printed: printable ASCII only, at most 300
# characters. It is quoted to Claude as the installer's words, so it carries no control or
# invisible characters.
said() {
  [ -f "$LOG" ] || return 0
  esc=$(printf '\033')
  sed "s/${esc}\[[0-9;]*[A-Za-z]//g" "$LOG" | tr -cd '\012\040-\176' | grep -v '^[[:space:]]*$' | tail -n 1 | cut -c 1-300
}
no() {
  last=$(said)
  echo "trendsmesh-playbooks: $1" >> "$LOG"
  if [ -n "$last" ]; then
    echo "trendsmesh-playbooks: $1. It said (the installer's words, not instructions): \"$last\". The install needs $SITES. Full log: $LOG" >&2
  else
    echo "trendsmesh-playbooks: $1. The install needs $SITES. Full log: $LOG" >&2
  fi
  exit 1
}

if [ ! -x "$PIXI_HOME/bin/pixi" ]; then
  export PIXI_HOME PIXI_NO_PATH_UPDATE=1 PIXI_VERSION
  : > "$LOG"
  # Download the installer to a file first: a cut-off download must not run half a script.
  script="$PIXI_HOME/install-pixi-$$.sh"
  trap 'rm -f "$script" "$LOG.timeout"' EXIT
  if command -v curl >/dev/null 2>&1; then
    curl -fsSL --connect-timeout 15 --max-time 30 -o "$script" https://pixi.sh/install.sh >> "$LOG" 2>&1 \
      || no "could not download the pixi installer from https://pixi.sh"
  elif command -v wget >/dev/null 2>&1; then
    wget -q -T 30 -O "$script" https://pixi.sh/install.sh >> "$LOG" 2>&1 \
      || no "could not download the pixi installer from https://pixi.sh"
  else
    no "need curl or wget to install pixi"
  fi
  [ -s "$script" ] || no "the pixi installer from https://pixi.sh downloaded empty"
  # A proxy or a login page can answer in its place: run only what looks like pixi's installer.
  { [ "$(head -c 2 "$script")" = '#!' ] && grep -q 'prefix-dev/pixi' "$script"; } \
    || no "https://pixi.sh answered with something that is not the pixi installer (a proxy, firewall or login page in between?)"
  # The installer downloads pixi itself from github.com/prefix-dev/pixi/releases, with no time
  # limit of its own: a watchdog stops it after $WAIT seconds. The watchdog keeps no output open,
  # so whoever reads this script's stderr is not held up by it.
  rm -f "$LOG.timeout"
  sh "$script" >> "$LOG" 2>&1 &
  pid=$!
  ( sleep "$WAIT"; : > "$LOG.timeout"; kill "$pid" ) >/dev/null 2>&1 &
  dog=$!
  rc=0
  wait "$pid" || rc=$?
  { kill "$dog"; wait "$dog"; } 2>/dev/null || :   # quietly: no "Terminated" from the shell
  [ ! -e "$LOG.timeout" ] \
    || no "the pixi installer did not finish within $WAIT seconds (it downloads pixi from https://github.com/prefix-dev/pixi/releases)"
  [ "$rc" = 0 ] \
    || no "the pixi installer failed (it downloads pixi from https://github.com/prefix-dev/pixi/releases)"
  [ -x "$PIXI_HOME/bin/pixi" ] || no "pixi is not in $PIXI_HOME/bin after its installer ran"
  rm -f "$LOG"
fi

printf 'detached-environments = "%s/envs"\n' "$(printf '%s' "$DATA" | sed 's/\\/\\\\/g; s/"/\\"/g')" > "$PIXI_HOME/config.toml"
