"""Thread-safe state-machine simulation of an automated pencil assembly line."""

from __future__ import annotations

import copy
import logging
import math
import os
import random
import threading
import time
from datetime import datetime, timezone
from typing import Any

from .influx_writer import InfluxConfig, InfluxWriter
from .models import MachineState, ProductRecord, ProductionSnapshot, Stage, STAGE_SEQUENCE

LOGGER = logging.getLogger(__name__)


def _utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _escape_tag(value: str) -> str:
    return value.replace(" ", r"\ ").replace(",", r"\,").replace("=", r"\=")


def _escape_string_field(value: str) -> str:
    return value.replace("\\", r"\\").replace('"', r'\"')


class ProductionLine:
    """Simulates production, defects, faults, controls, and telemetry."""

    STAGE_DEFECTS: dict[Stage, tuple[str, ...]] = {
        Stage.BODY_FEED: ("Cracked wooden body", "Body missing from feeder"),
        Stage.GRAPHITE_INSERTION: ("Graphite core misaligned", "Graphite core broken"),
        Stage.FERRULE_INSTALLATION: ("Ferrule not fully seated", "Ferrule clamp force too low"),
        Stage.ERASER_INSERTION: ("Eraser missing", "Eraser insertion depth out of tolerance"),
        Stage.QUALITY_INSPECTION: (
            "Overall pencil length out of tolerance",
            "Visual surface defect detected",
        ),
    }

    MACHINE_FAULTS: tuple[str, ...] = (
        "Conveyor jam detected at station 3",
        "Photoelectric sensor timeout",
        "Safety guard interlock opened",
        "Drive motor overtemperature",
    )

    def __init__(self, seed: int | None = None):
        self._lock = threading.RLock()
        self._run_event = threading.Event()
        self._shutdown = threading.Event()
        self._rng = random.Random(seed)
        self._started_at = time.monotonic()
        self._product_started_at = 0.0
        self._pending_product_defect = ""
        self._pending_measurements: dict[str, float | str | bool] = {}
        self.snapshot = ProductionSnapshot(
            target_cycle_s=float(os.getenv("TARGET_CYCLE_SECONDS", "5.4")),
            defect_probability=float(os.getenv("DEFECT_PROBABILITY", "0.08")),
            machine_speed=float(os.getenv("MACHINE_SPEED", "1.0")),
        )
        self._add_event("System initialized", "INFO")

        influx_config = InfluxConfig(
            enabled=os.getenv("INFLUXDB_ENABLED", "true").lower() in {"1", "true", "yes"},
            url=os.getenv("INFLUXDB_URL", "http://localhost:8086"),
            org=os.getenv("INFLUXDB_ORG", "srh"),
            bucket=os.getenv("INFLUXDB_BUCKET", "pencil_production"),
            token=os.getenv("INFLUXDB_TOKEN", "srh-pencils-super-secret-token"),
        )
        self.influx = InfluxWriter(influx_config, self._set_database_status)
        self._thread = threading.Thread(target=self._loop, name="production-line", daemon=True)
        self._thread.start()

    def close(self) -> None:
        self._shutdown.set()
        self._run_event.set()
        self._thread.join(timeout=3)
        self.influx.close()

    def _set_database_status(self, connected: bool) -> None:
        with self._lock:
            self.snapshot.database_connected = connected

    def _add_event(self, message: str, level: str = "INFO") -> None:
        event = {"time": datetime.now().strftime("%H:%M:%S"), "level": level, "message": message}
        self.snapshot.event_log.insert(0, event)
        del self.snapshot.event_log[30:]

    def get_snapshot(self) -> dict[str, Any]:
        with self._lock:
            self.snapshot.uptime_s = round(time.monotonic() - self._started_at, 1)
            total = self.snapshot.total_count
            self.snapshot.yield_percent = round(
                (self.snapshot.good_count / total * 100.0) if total else 100.0, 1
            )
            return copy.deepcopy(self.snapshot.to_dict())

    def start(self) -> tuple[bool, str]:
        with self._lock:
            if self.snapshot.state in {MachineState.FAULT, MachineState.EMERGENCY_STOP}:
                return False, "Clear or acknowledge the active fault before starting."
            if self.snapshot.state == MachineState.RUNNING:
                return True, "Production line is already running."
            self.snapshot.state = MachineState.RUNNING
            self.snapshot.fault_message = ""
            self._add_event("START command accepted", "SUCCESS")
            self._run_event.set()
            self._publish_telemetry(event="start")
            return True, "Production started."

    def stop(self) -> tuple[bool, str]:
        with self._lock:
            if self.snapshot.state != MachineState.RUNNING:
                return False, "The production line is not running."
            self.snapshot.state = MachineState.STOPPED
            self._run_event.clear()
            self._add_event("STOP command accepted; cycle paused", "WARNING")
            self._publish_telemetry(event="stop")
            return True, "Production stopped."

    def reset(self) -> tuple[bool, str]:
        with self._lock:
            if self.snapshot.state == MachineState.RUNNING:
                return False, "Stop the line before resetting counters."
            settings = (
                self.snapshot.target_cycle_s,
                self.snapshot.defect_probability,
                self.snapshot.machine_speed,
            )
            database_connected = self.snapshot.database_connected
            self.snapshot = ProductionSnapshot(
                database_connected=database_connected,
                target_cycle_s=settings[0],
                defect_probability=settings[1],
                machine_speed=settings[2],
            )
            self._pending_product_defect = ""
            self._pending_measurements = {}
            self._add_event("Counters and product history reset", "INFO")
            self._publish_telemetry(event="reset")
            return True, "Production data reset."

    def emergency_stop(self) -> tuple[bool, str]:
        with self._lock:
            self.snapshot.state = MachineState.EMERGENCY_STOP
            self.snapshot.fault_message = "Emergency stop activated by operator"
            self._run_event.clear()
            self._add_event(self.snapshot.fault_message, "CRITICAL")
            self._publish_telemetry(event="emergency_stop")
            return True, "Emergency stop activated."

    def acknowledge_fault(self) -> tuple[bool, str]:
        with self._lock:
            if self.snapshot.state not in {MachineState.FAULT, MachineState.EMERGENCY_STOP}:
                return False, "There is no active fault to acknowledge."
            previous = self.snapshot.fault_message or self.snapshot.state.value
            self.snapshot.state = MachineState.STOPPED
            self.snapshot.stage = Stage.WAITING
            self.snapshot.stage_index = -1
            self.snapshot.current_product_id = None
            self.snapshot.fault_message = ""
            self._pending_product_defect = ""
            self._pending_measurements = {}
            self._add_event(f"Fault acknowledged: {previous}", "INFO")
            self._publish_telemetry(event="fault_acknowledged")
            return True, "Fault cleared. Press Start to resume."

    def inject_fault(self, message: str | None = None) -> tuple[bool, str]:
        with self._lock:
            if self.snapshot.state != MachineState.RUNNING:
                return False, "Start the line before injecting a demonstration fault."
            self._trigger_fault(message or "Demonstration fault: sensor signal lost")
            return True, "Fault injected for demonstration."

    def update_settings(self, machine_speed: float, defect_probability: float) -> tuple[bool, str]:
        if not 0.5 <= machine_speed <= 2.0:
            return False, "Machine speed must be between 0.5x and 2.0x."
        if not 0.0 <= defect_probability <= 0.35:
            return False, "Defect probability must be between 0% and 35%."
        with self._lock:
            self.snapshot.machine_speed = round(machine_speed, 2)
            self.snapshot.defect_probability = round(defect_probability, 3)
            self._add_event(
                f"Settings updated: speed {machine_speed:.2f}x, defect probability {defect_probability:.1%}",
                "INFO",
            )
            return True, "Settings updated."

    def _loop(self) -> None:
        while not self._shutdown.is_set():
            if not self._run_event.wait(timeout=0.25):
                self._cool_machine()
                continue
            if self._shutdown.is_set():
                break
            with self._lock:
                if self.snapshot.state != MachineState.RUNNING:
                    self._run_event.clear()
                    continue
            self._run_product_cycle()

    def _run_product_cycle(self) -> None:
        with self._lock:
            product_id = self.snapshot.total_count + 1
            self.snapshot.current_product_id = product_id
            self._product_started_at = time.monotonic()
            self._pending_product_defect = ""
            self._pending_measurements = {}
            self._add_event(f"Pencil #{product_id} entered the line", "INFO")

        for index, stage in enumerate(STAGE_SEQUENCE):
            with self._lock:
                if self.snapshot.state != MachineState.RUNNING:
                    return
                self.snapshot.stage = stage
                self.snapshot.stage_index = index
                self._update_temperature(running=True)
                self._generate_stage_measurements(stage)
                self._publish_telemetry(event="stage")

            if not self._interruptible_sleep(self._stage_duration(stage)):
                return

            with self._lock:
                if self.snapshot.state != MachineState.RUNNING:
                    return
                self._evaluate_stage_defect(stage)
                # Low-probability equipment fault, independent of product quality.
                if self._rng.random() < 0.0015:
                    self._trigger_fault(self._rng.choice(self.MACHINE_FAULTS))
                    return

        with self._lock:
            if self.snapshot.state == MachineState.RUNNING:
                self._complete_product(product_id)

    def _interruptible_sleep(self, duration_s: float) -> bool:
        deadline = time.monotonic() + duration_s
        while time.monotonic() < deadline:
            if self._shutdown.is_set():
                return False
            with self._lock:
                if self.snapshot.state != MachineState.RUNNING:
                    return False
            time.sleep(min(0.08, deadline - time.monotonic()))
        return True

    def _stage_duration(self, stage: Stage) -> float:
        weights = {
            Stage.BODY_FEED: 0.65,
            Stage.GRAPHITE_INSERTION: 1.05,
            Stage.FERRULE_INSTALLATION: 0.90,
            Stage.ERASER_INSERTION: 0.80,
            Stage.QUALITY_INSPECTION: 1.20,
            Stage.SORTING: 0.55,
        }
        base_total = sum(weights.values())
        target = self.snapshot.target_cycle_s
        return weights[stage] / base_total * target / self.snapshot.machine_speed

    def _generate_stage_measurements(self, stage: Stage) -> None:
        if stage == Stage.BODY_FEED:
            self._pending_measurements["body_length_mm"] = round(self._rng.gauss(175.0, 0.35), 2)
            self._pending_measurements["body_present"] = True
        elif stage == Stage.GRAPHITE_INSERTION:
            self._pending_measurements["graphite_offset_mm"] = round(abs(self._rng.gauss(0.18, 0.10)), 2)
            self._pending_measurements["graphite_integrity"] = "OK"
        elif stage == Stage.FERRULE_INSTALLATION:
            self._pending_measurements["ferrule_force_n"] = round(self._rng.gauss(42.0, 2.0), 1)
        elif stage == Stage.ERASER_INSERTION:
            self._pending_measurements["eraser_depth_mm"] = round(self._rng.gauss(8.0, 0.3), 2)
            self._pending_measurements["eraser_present"] = True
        elif stage == Stage.QUALITY_INSPECTION:
            self._pending_measurements["final_length_mm"] = round(self._rng.gauss(190.0, 0.45), 2)
            self._pending_measurements["surface_score"] = round(self._rng.uniform(92.0, 100.0), 1)

    def _evaluate_stage_defect(self, stage: Stage) -> None:
        if self._pending_product_defect or stage not in self.STAGE_DEFECTS:
            return
        # Distribute the configured final-product defect probability across five inspection points.
        per_stage_probability = 1.0 - math.pow(1.0 - self.snapshot.defect_probability, 1.0 / 5.0)
        if self._rng.random() >= per_stage_probability:
            return

        reason = self._rng.choice(self.STAGE_DEFECTS[stage])
        self._pending_product_defect = reason
        if reason == "Body missing from feeder":
            self._pending_measurements["body_present"] = False
        elif reason == "Graphite core misaligned":
            self._pending_measurements["graphite_offset_mm"] = round(self._rng.uniform(0.7, 1.4), 2)
        elif reason == "Graphite core broken":
            self._pending_measurements["graphite_integrity"] = "BROKEN"
        elif reason == "Ferrule clamp force too low":
            self._pending_measurements["ferrule_force_n"] = round(self._rng.uniform(26.0, 34.0), 1)
        elif reason == "Eraser missing":
            self._pending_measurements["eraser_present"] = False
        elif reason == "Eraser insertion depth out of tolerance":
            self._pending_measurements["eraser_depth_mm"] = round(self._rng.choice([self._rng.uniform(5.5, 6.5), self._rng.uniform(9.6, 10.5)]), 2)
        elif reason == "Overall pencil length out of tolerance":
            self._pending_measurements["final_length_mm"] = round(self._rng.choice([self._rng.uniform(186.0, 188.2), self._rng.uniform(192.0, 194.0)]), 2)
        elif reason == "Visual surface defect detected":
            self._pending_measurements["surface_score"] = round(self._rng.uniform(55.0, 78.0), 1)

    def _complete_product(self, product_id: int) -> None:
        elapsed = round(time.monotonic() - self._product_started_at, 2)
        defective = bool(self._pending_product_defect)
        result = "DEFECTIVE" if defective else "GOOD"
        reason = self._pending_product_defect or "None"
        self.snapshot.total_count += 1
        if defective:
            self.snapshot.defect_count += 1
            self.snapshot.last_defect_reason = reason
            self._add_event(f"Pencil #{product_id} rejected: {reason}", "ERROR")
        else:
            self.snapshot.good_count += 1
            self._add_event(f"Pencil #{product_id} passed final inspection", "SUCCESS")
        self.snapshot.last_cycle_time_s = elapsed
        record = ProductRecord(
            product_id=product_id,
            result=result,
            defect_reason=reason,
            cycle_time_s=elapsed,
            completed_at=_utc_iso(),
            measurements=copy.deepcopy(self._pending_measurements),
        )
        self.snapshot.recent_products.insert(0, record)
        del self.snapshot.recent_products[12:]
        self.snapshot.stage = Stage.SORTING
        self.snapshot.stage_index = len(STAGE_SEQUENCE) - 1
        self._publish_telemetry(event="product_complete", defective=defective, defect_reason=reason)
        self.snapshot.current_product_id = None

    def _trigger_fault(self, message: str) -> None:
        self.snapshot.state = MachineState.FAULT
        self.snapshot.fault_message = message
        self._run_event.clear()
        self._add_event(message, "CRITICAL")
        self._publish_telemetry(event="machine_fault")

    def _update_temperature(self, running: bool) -> None:
        target = 38.0 if running else 24.0
        drift = (target - self.snapshot.temperature_c) * (0.025 if running else 0.012)
        noise = self._rng.uniform(-0.12, 0.18 if running else 0.08)
        self.snapshot.temperature_c = round(max(20.0, min(70.0, self.snapshot.temperature_c + drift + noise)), 1)
        if running and self.snapshot.temperature_c > 58.0:
            self._trigger_fault("Drive motor overtemperature")

    def _cool_machine(self) -> None:
        with self._lock:
            self._update_temperature(running=False)

    def _publish_telemetry(
        self,
        event: str,
        defective: bool = False,
        defect_reason: str = "",
    ) -> None:
        state_code = {
            MachineState.IDLE: 0,
            MachineState.RUNNING: 1,
            MachineState.STOPPED: 2,
            MachineState.FAULT: 3,
            MachineState.EMERGENCY_STOP: 4,
        }[self.snapshot.state]
        stage_tag = _escape_tag(self.snapshot.stage.value.replace(" ", "_"))
        state_tag = _escape_tag(self.snapshot.state.value)
        event_tag = _escape_tag(event)
        fields = [
            f"temperature={self.snapshot.temperature_c}",
            f"total_count={self.snapshot.total_count}i",
            f"good_count={self.snapshot.good_count}i",
            f"defect_count={self.snapshot.defect_count}i",
            f"cycle_time={self.snapshot.last_cycle_time_s}",
            f"state_code={state_code}i",
            f"stage_index={self.snapshot.stage_index}i",
            f"defective={1 if defective else 0}i",
            f"yield_percent={self.snapshot.yield_percent}",
            f'machine_state="{_escape_string_field(self.snapshot.state.value)}"',
            f'defect_reason="{_escape_string_field(defect_reason or self.snapshot.last_defect_reason)}"',
        ]
        timestamp_ms = int(time.time() * 1000)
        line = (
            f"production_metrics,machine=pencil_line,state={state_tag},stage={stage_tag},event={event_tag} "
            + ",".join(fields)
            + f" {timestamp_ms}"
        )
        self.influx.enqueue(line)
