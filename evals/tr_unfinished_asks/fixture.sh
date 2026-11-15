#!/bin/bash
# Workspace for this case: the engine shim (./tm.sh) and the run folder, built by _lib/.
exec bash "$(dirname "${BASH_SOURCE[0]}")/../_lib/scaffold.sh" tr_at_b3
