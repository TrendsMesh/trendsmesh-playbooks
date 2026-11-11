"""A stand-in for the TrendsMesh inbox (`POST /v1/issue-reports`) for the report-issue evals.

    fake_inbox.py <workspace> <201|404> [lifetime seconds]

Listens on 127.0.0.1 on a free port, writes the port to `<workspace>/fake-inbox/port`, records each
request as one JSON line in `<workspace>/fake-inbox/requests.jsonl` (method, path, the JSON body)
and answers every POST with the given status: 201 with a report id, or 404 (the inbox before it
is live). It stops by itself after the lifetime (default 30 minutes), so
a case never leaves it running. Standard library only.
"""

from __future__ import annotations

import json
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

REPORT_ID = "rpt_test_0001"


def main() -> int:
    workspace = Path(sys.argv[1])
    status = int(sys.argv[2])
    lifetime = float(sys.argv[3]) if len(sys.argv) > 3 else 1800.0
    folder = workspace / "fake-inbox"
    folder.mkdir(parents=True, exist_ok=True)
    log = folder / "requests.jsonl"
    log.touch()
    lock = threading.Lock()

    class Handler(BaseHTTPRequestHandler):
        def _reply(self, code: int, payload: dict) -> None:
            raw = json.dumps(payload).encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)

        def do_POST(self) -> None:  # noqa: N802 (http.server's name)
            length = int(self.headers.get("Content-Length") or 0)
            raw = self.rfile.read(length)
            try:
                body: object = json.loads(raw.decode("utf-8"))
            except ValueError:
                body = raw.decode("utf-8", "replace")
            with lock, log.open("a", encoding="utf-8") as out:
                out.write(json.dumps({"method": "POST", "path": self.path, "answered": status,
                                      "body": body}) + "\n")
            if status == 201:
                self._reply(201, {"data": {"reportId": REPORT_ID, "status": "received"}})
            else:
                self._reply(status, {"error": {"code": "not_found", "message": "Not found"}})

        def log_message(self, *args: object) -> None:  # keep the scaffold's output quiet
            return

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    (folder / "port").write_text(str(server.server_address[1]), encoding="utf-8")
    timer = threading.Timer(lifetime, server.shutdown)
    timer.daemon = True
    timer.start()
    server.serve_forever()
    return 0


if __name__ == "__main__":
    sys.exit(main())
