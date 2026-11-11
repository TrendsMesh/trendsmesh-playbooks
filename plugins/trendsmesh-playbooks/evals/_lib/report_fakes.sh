#!/bin/bash
# The fakes for the report-issue cases (ri_*): runs in the workspace, after scaffold.sh.
#   report_fakes.sh <gh: signed_in|none> <inbox: 201|404>
# - gh: `signed_in` writes a fake GitHub CLI at fakebin/gh. It records every call, one line per call,
#   in fake-gh/calls.log, and the body it is given on stdin in fake-gh/issue-body.md; `auth status`
#   succeeds and `issue create` prints an issue link. `none` writes no gh at all.
#   ./gh.sh is the same gh for the agent's own calls (the harness note maps `gh` to it); without a gh
#   it answers like a shell that has none ("command not found", exit 127).
# - inbox: starts fake_inbox.py on a free local port, answering 201 or 404, and recording each
#   request in fake-inbox/requests.jsonl.
# - .tm-env, which ./tm.sh reads: PATH is fakebin and the system folders only, so `tm report github`
#   finds the fake gh or none (never the developer's own gh), and TM_REPORT_URL is the fake inbox.
set -euo pipefail
LIB="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WS="$PWD"
GH_MODE="${1:?gh mode: signed_in|none}"
INBOX_STATUS="${2:?inbox status: 201|404}"

mkdir -p "$WS/fakebin" "$WS/fake-gh"
: > "$WS/fake-gh/calls.log"

case "$GH_MODE" in
  signed_in)
    cat > "$WS/fakebin/gh" <<SH
#!/bin/sh
# A fake GitHub CLI for the report-issue evals: records each call and never reaches GitHub.
LOG="$WS/fake-gh/calls.log"
line="gh"
for a in "\$@"; do line="\$line \$a"; done
printf '%s\n' "\$line" >> "\$LOG"
case "\$1 \$2" in
  "auth status")
    echo "github.com" >&2
    echo "  Logged in to github.com account sample-tester (keyring)" >&2
    exit 0 ;;
  "issue create")
    cat >> "$WS/fake-gh/issue-body.md"
    echo "Creating issue in TrendsMesh/trendsmesh-playbooks" >&2
    echo "https://github.com/TrendsMesh/trendsmesh-playbooks/issues/321"
    exit 0 ;;
  *)
    echo "fake gh: this call is not part of the test: \$*" >&2
    exit 1 ;;
esac
SH
    chmod +x "$WS/fakebin/gh"
    cat > "$WS/gh.sh" <<SH
#!/bin/sh
exec "$WS/fakebin/gh" "\$@"
SH
    ;;
  none)
    cat > "$WS/gh.sh" <<'SH'
#!/bin/sh
echo "sh: gh: command not found" >&2
exit 127
SH
    ;;
  *) echo "report_fakes.sh: unknown gh mode $GH_MODE" >&2; exit 2 ;;
esac
chmod +x "$WS/gh.sh"

# The inbox: started detached, so it outlives this script; it stops by itself after 30 minutes.
PY="$(command -v python3)"
nohup "$PY" "$LIB/fake_inbox.py" "$WS" "$INBOX_STATUS" 1800 </dev/null >/dev/null 2>&1 &
for _ in $(seq 1 100); do
  [ -s "$WS/fake-inbox/port" ] && break
  sleep 0.1
done
[ -s "$WS/fake-inbox/port" ] || { echo "report_fakes.sh: the fake inbox did not start" >&2; exit 1; }
PORT="$(cat "$WS/fake-inbox/port")"

# The eval's Bash sandbox refuses a direct connection to 127.0.0.1, and its NO_PROXY sends local
# addresses direct. Without NO_PROXY, tm's urllib goes through the sandbox's proxy, which lets
# 127.0.0.1 through only because evals/run.sh grants WebFetch(domain:127.0.0.1).
cat > "$WS/.tm-env" <<SH
export PATH="$WS/fakebin:/usr/bin:/bin:/usr/sbin:/sbin"
export TM_REPORT_URL="http://127.0.0.1:$PORT/v1/issue-reports"
unset NO_PROXY no_proxy
SH
