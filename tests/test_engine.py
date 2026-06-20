import os
import time
import unittest

os.environ["INFLUXDB_ENABLED"] = "false"
os.environ["TARGET_CYCLE_SECONDS"] = "0.18"

from production_line.engine import ProductionLine  # noqa: E402
from production_line.models import MachineState  # noqa: E402


class ProductionLineTests(unittest.TestCase):
    def setUp(self):
        self.line = ProductionLine(seed=7)

    def tearDown(self):
        self.line.close()

    def wait_for(self, predicate, timeout=2.0):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if predicate():
                return True
            time.sleep(0.02)
        return False

    def test_start_produces_products(self):
        ok, _ = self.line.update_settings(2.0, 0.0)
        self.assertTrue(ok)
        ok, _ = self.line.start()
        self.assertTrue(ok)
        self.assertTrue(self.wait_for(lambda: self.line.get_snapshot()["total_count"] >= 1))
        snapshot = self.line.get_snapshot()
        self.assertEqual(snapshot["good_count"], snapshot["total_count"])
        self.assertEqual(snapshot["defect_count"], 0)

    def test_stop_and_reset(self):
        self.line.start()
        time.sleep(0.04)
        ok, _ = self.line.stop()
        self.assertTrue(ok)
        self.assertEqual(self.line.get_snapshot()["state"], MachineState.STOPPED.value)
        ok, _ = self.line.reset()
        self.assertTrue(ok)
        snapshot = self.line.get_snapshot()
        self.assertEqual(snapshot["total_count"], 0)
        self.assertEqual(snapshot["state"], MachineState.IDLE.value)

    def test_emergency_stop_requires_acknowledgement(self):
        self.line.start()
        self.line.emergency_stop()
        snapshot = self.line.get_snapshot()
        self.assertEqual(snapshot["state"], MachineState.EMERGENCY_STOP.value)
        ok, _ = self.line.start()
        self.assertFalse(ok)
        ok, _ = self.line.acknowledge_fault()
        self.assertTrue(ok)
        self.assertEqual(self.line.get_snapshot()["state"], MachineState.STOPPED.value)

    def test_settings_validation(self):
        ok, _ = self.line.update_settings(2.5, 0.1)
        self.assertFalse(ok)
        ok, _ = self.line.update_settings(1.2, 0.5)
        self.assertFalse(ok)
        ok, _ = self.line.update_settings(1.2, 0.15)
        self.assertTrue(ok)

    def test_injected_fault(self):
        self.line.start()
        ok, _ = self.line.inject_fault("Unit-test conveyor jam")
        self.assertTrue(ok)
        snapshot = self.line.get_snapshot()
        self.assertEqual(snapshot["state"], MachineState.FAULT.value)
        self.assertIn("conveyor jam", snapshot["fault_message"].lower())


if __name__ == "__main__":
    unittest.main()
