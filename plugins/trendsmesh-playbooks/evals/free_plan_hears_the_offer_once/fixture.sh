#!/bin/bash
# Workspace for this case: the engine shim (./tm.sh) and TrendsMesh's public plans answer, built by _lib/.
exec bash "$(dirname "${BASH_SOURCE[0]}")/../_lib/scaffold.sh" plans_offer
