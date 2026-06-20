"""HTTP server and JSON API for the browser-based HMI."""

from __future__ import annotations

import json
import logging
import mimetypes
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from .engine import ProductionLine

LOGGER = logging.getLogger(__name__)


class HMIServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True

    def __init__(self, server_address: tuple[str, int], static_dir: Path, line: ProductionLine):
        self.static_dir = static_dir.resolve()
        self.line = line
        super().__init__(server_address, HMIRequestHandler)


class HMIRequestHandler(BaseHTTPRequestHandler):
    server: HMIServer

    def log_message(self, format: str, *args: Any) -> None:
        LOGGER.info("%s - %s", self.address_string(), format % args)

    def _send_json(self, payload: dict[str, Any], status: int = HTTPStatus.OK) -> None:
        body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _read_json(self) -> dict[str, Any]:
        length = int(self.headers.get("Content-Length", "0"))
        if length <= 0:
            return {}
        if length > 65_536:
            raise ValueError("Request body too large")
        raw = self.rfile.read(length)
        return json.loads(raw.decode("utf-8"))

    def _serve_static(self, request_path: str) -> None:
        relative = "index.html" if request_path in {"", "/"} else request_path.lstrip("/")
        candidate = (self.server.static_dir / relative).resolve()
        if self.server.static_dir not in candidate.parents and candidate != self.server.static_dir:
            self.send_error(HTTPStatus.FORBIDDEN)
            return
        if not candidate.exists() or not candidate.is_file():
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        content = candidate.read_bytes()
        content_type = mimetypes.guess_type(candidate.name)[0] or "application/octet-stream"
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", f"{content_type}; charset=utf-8" if content_type.startswith("text/") else content_type)
        self.send_header("Content-Length", str(len(content)))
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        self.wfile.write(content)

    def do_GET(self) -> None:  # noqa: N802
        path = urlparse(self.path).path
        if path == "/api/status":
            self._send_json(self.server.line.get_snapshot())
        elif path == "/health":
            self._send_json({"status": "ok", "service": "pencil-line-hmi"})
        else:
            self._serve_static(path)

    def do_POST(self) -> None:  # noqa: N802
        path = urlparse(self.path).path
        try:
            payload = self._read_json()
            actions = {
                "/api/start": self.server.line.start,
                "/api/stop": self.server.line.stop,
                "/api/reset": self.server.line.reset,
                "/api/emergency-stop": self.server.line.emergency_stop,
                "/api/acknowledge": self.server.line.acknowledge_fault,
            }
            if path in actions:
                ok, message = actions[path]()
            elif path == "/api/inject-fault":
                ok, message = self.server.line.inject_fault(payload.get("message"))
            elif path == "/api/settings":
                ok, message = self.server.line.update_settings(
                    float(payload.get("machine_speed", 1.0)),
                    float(payload.get("defect_probability", 0.08)),
                )
            else:
                self._send_json({"ok": False, "message": "Unknown API endpoint"}, HTTPStatus.NOT_FOUND)
                return
            self._send_json({"ok": ok, "message": message}, HTTPStatus.OK if ok else HTTPStatus.CONFLICT)
        except (ValueError, TypeError, json.JSONDecodeError) as exc:
            self._send_json({"ok": False, "message": str(exc)}, HTTPStatus.BAD_REQUEST)
        except Exception as exc:  # pragma: no cover - defensive API boundary
            LOGGER.exception("Unhandled API error")
            self._send_json({"ok": False, "message": "Internal server error"}, HTTPStatus.INTERNAL_SERVER_ERROR)
