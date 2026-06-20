import json
import os
import threading
import time
import unittest
import urllib.request
from pathlib import Path

os.environ["INFLUXDB_ENABLED"] = "false"
os.environ["TARGET_CYCLE_SECONDS"] = "0.2"

from production_line.engine import ProductionLine  # noqa: E402
from production_line.web_server import HMIServer  # noqa: E402


class APITests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.line = ProductionLine(seed=11)
        static_dir = Path(__file__).parents[1] / "static"
        cls.server = HMIServer(("127.0.0.1", 0), static_dir, cls.line)
        cls.port = cls.server.server_address[1]
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        time.sleep(0.05)

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.line.close()

    def request_json(self, path, method="GET", payload=None):
        data = None if payload is None else json.dumps(payload).encode()
        request = urllib.request.Request(
            f"http://127.0.0.1:{self.port}{path}", data=data, method=method,
            headers={"Content-Type": "application/json"}
        )
        with urllib.request.urlopen(request, timeout=2) as response:
            return response.status, json.loads(response.read())

    def test_status_endpoint(self):
        status, payload = self.request_json("/api/status")
        self.assertEqual(status, 200)
        self.assertIn("state", payload)
        self.assertIn("temperature_c", payload)

    def test_start_endpoint(self):
        self.line.acknowledge_fault()
        if self.line.get_snapshot()["state"] == "RUNNING":
            self.line.stop()
        status, payload = self.request_json("/api/start", "POST", {})
        self.assertEqual(status, 200)
        self.assertTrue(payload["ok"])

    def test_static_hmi(self):
        with urllib.request.urlopen(f"http://127.0.0.1:{self.port}/", timeout=2) as response:
            body = response.read().decode()
        self.assertIn("PencilLine", body)
        self.assertIn("Machine controls", body)


if __name__ == "__main__":
    unittest.main()
