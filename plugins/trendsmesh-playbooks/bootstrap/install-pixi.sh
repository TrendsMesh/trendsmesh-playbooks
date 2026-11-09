#!/bin/sh
# Installs pixi into <data>/pixi if missing, and points its environments at <data>/envs.
# PIXI_NO_PATH_UPDATE keeps the user's shell profile untouched. PIXI_VERSION pins the pixi that
# CI and the lock file were made with: another pixi may read the lock and --frozen differently
# (keep it equal to pixi-version in .github/workflows/ci.yml and install-pixi.ps1).
# Exits non-zero, with the reason on stderr, when pixi is not there afterwards.
set -eu
DATA=${CLAUDE_PLUGIN_DATA:?CLAUDE_PLUGIN_DATA is not set}
PIXI_HOME="$DATA/pixi"
PIXI_VERSION=v0.84.1
mkdir -p "$PIXI_HOME"
no() { echo "trendsmesh-playbooks: $1" >&2; exit 1; }

if [ ! -x "$PIXI_HOME/bin/pixi" ]; then
  export PIXI_HOME PIXI_NO_PATH_UPDATE=1 PIXI_VERSION
  # Download the installer to a file first: a cut-off download must not run half a script.
  script="$PIXI_HOME/install-pixi-$$.sh"
  trap 'rm -f "$script"' EXIT
  if command -v curl >/dev/null 2>&1; then
    curl -fsSL --connect-timeout 20 --max-time 120 -o "$script" https://pixi.sh/install.sh \
      || no "could not download the pixi installer from pixi.sh (no internet connection, or a proxy or firewall blocks it)"
  elif command -v wget >/dev/null 2>&1; then
    wget -q -T 60 -O "$script" https://pixi.sh/install.sh \
      || no "could not download the pixi installer from pixi.sh (no internet connection, or a proxy or firewall blocks it)"
  else
    no "need curl or wget to install pixi"
  fi
  [ -s "$script" ] || no "the pixi installer downloaded empty"
  sh "$script" >&2 || no "the pixi installer failed"
  [ -x "$PIXI_HOME/bin/pixi" ] || no "pixi is not in $PIXI_HOME/bin after its installer ran"
fi

printf 'detached-environments = "%s/envs"\n' "$(printf '%s' "$DATA" | sed 's/\\/\\\\/g; s/"/\\"/g')" > "$PIXI_HOME/config.toml"
