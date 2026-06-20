"""Application entry point for the automated pencil production line HMI."""

from __future__ import annotations

import logging
import os
import signal
import sys
from pathlib import Path

from production_line.engine import ProductionLine
from production_line.web_server import HMIServer


def main() -> int:
    logging.basicConfig(
        level=os.getenv("LOG_LEVEL", "INFO"),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "8000"))
    static_dir = Path(__file__).parent / "static"
    line = ProductionLine()
    server = HMIServer((host, port), static_dir=static_dir, line=line)

    def shutdown_handler(signum: int, frame: object) -> None:
        del frame
        logging.getLogger(__name__).info("Received signal %s; shutting down", signum)
        server.shutdown()

    signal.signal(signal.SIGTERM, shutdown_handler)
    signal.signal(signal.SIGINT, shutdown_handler)

    logging.getLogger(__name__).info("HMI available at http://%s:%s", host, port)
    try:
        server.serve_forever(poll_interval=0.2)
    finally:
        server.server_close()
        line.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
