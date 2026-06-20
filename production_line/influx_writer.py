"""Minimal, dependency-free InfluxDB v2 writer using the HTTP API."""

from __future__ import annotations

import json
import logging
import queue
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Callable

LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class InfluxConfig:
    enabled: bool
    url: str
    org: str
    bucket: str
    token: str
    timeout_s: float = 1.5


class InfluxWriter:
    """Write telemetry in the background so database delays never block production."""

    def __init__(self, config: InfluxConfig, status_callback: Callable[[bool], None] | None = None):
        self.config = config
        self.status_callback = status_callback
        self.connected = False
        self.last_error = ""
        self._queue: queue.Queue[str | None] = queue.Queue(maxsize=1000)
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._worker, name="influx-writer", daemon=True)
        self._thread.start()

    def close(self) -> None:
        self._stop.set()
        try:
            self._queue.put_nowait(None)
        except queue.Full:
            pass
        self._thread.join(timeout=2)

    def enqueue(self, line_protocol: str) -> None:
        if not self.config.enabled:
            return
        try:
            self._queue.put_nowait(line_protocol)
        except queue.Full:
            LOGGER.warning("InfluxDB queue full; dropping oldest telemetry sample")
            try:
                self._queue.get_nowait()
                self._queue.put_nowait(line_protocol)
            except queue.Empty:
                pass

    def _set_status(self, connected: bool, error: str = "") -> None:
        if connected != self.connected and self.status_callback:
            self.status_callback(connected)
        self.connected = connected
        self.last_error = error

    def _health_check(self) -> bool:
        if not self.config.enabled:
            self._set_status(False, "Database disabled for local preview")
            return False
        health_url = f"{self.config.url.rstrip('/')}/health"
        request = urllib.request.Request(health_url, method="GET")
        try:
            with urllib.request.urlopen(request, timeout=self.config.timeout_s) as response:
                payload = json.loads(response.read().decode("utf-8"))
                healthy = response.status == 200 and payload.get("status") == "pass"
                self._set_status(healthy, "" if healthy else "InfluxDB health check failed")
                return healthy
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
            self._set_status(False, str(exc))
            return False

    def _write(self, line_protocol: str) -> bool:
        query = urllib.parse.urlencode(
            {"org": self.config.org, "bucket": self.config.bucket, "precision": "ms"}
        )
        write_url = f"{self.config.url.rstrip('/')}/api/v2/write?{query}"
        request = urllib.request.Request(
            write_url,
            data=line_protocol.encode("utf-8"),
            method="POST",
            headers={
                "Authorization": f"Token {self.config.token}",
                "Content-Type": "text/plain; charset=utf-8",
                "Accept": "application/json",
            },
        )
        try:
            with urllib.request.urlopen(request, timeout=self.config.timeout_s) as response:
                ok = response.status == 204
                self._set_status(ok, "" if ok else f"Unexpected HTTP status {response.status}")
                return ok
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            self._set_status(False, f"HTTP {exc.code}: {body[:180]}")
        except (urllib.error.URLError, TimeoutError) as exc:
            self._set_status(False, str(exc))
        return False

    def _worker(self) -> None:
        next_health_check = 0.0
        while not self._stop.is_set():
            now = time.monotonic()
            if now >= next_health_check:
                self._health_check()
                next_health_check = now + 10.0

            try:
                item = self._queue.get(timeout=0.5)
            except queue.Empty:
                continue
            if item is None:
                break

            if not self._write(item):
                # One delayed retry is enough; the production line must keep running.
                time.sleep(0.75)
                self._write(item)
