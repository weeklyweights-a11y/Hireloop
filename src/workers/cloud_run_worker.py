"""Cloud Run entrypoint: Celery worker + HTTP health on $PORT."""
from __future__ import annotations

import os
import subprocess
import sys
from http.server import BaseHTTPRequestHandler, HTTPServer
from threading import Thread


class _HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:  # noqa: N802
        self.send_response(200)
        self.send_header("Content-Type", "text/plain")
        self.end_headers()
        self.wfile.write(b"ok")

    def log_message(self, format: str, *args) -> None:  # noqa: A003
        return


def main() -> None:
    port = int(os.environ.get("PORT", "8080"))
    server = HTTPServer(("0.0.0.0", port), _HealthHandler)
    Thread(target=server.serve_forever, daemon=True).start()

    cmd = [
        sys.executable,
        "-m",
        "celery",
        "-A",
        "src.workers.celery_app",
        "worker",
        "--loglevel=info",
        "--concurrency=4",
    ]
    raise SystemExit(subprocess.call(cmd))


if __name__ == "__main__":
    main()
