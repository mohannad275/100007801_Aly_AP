"""Domain models for the automated pencil production line."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any


class MachineState(str, Enum):
    IDLE = "IDLE"
    RUNNING = "RUNNING"
    STOPPED = "STOPPED"
    FAULT = "FAULT"
    EMERGENCY_STOP = "EMERGENCY_STOP"


class Stage(str, Enum):
    WAITING = "Waiting for start"
    BODY_FEED = "1. Wooden body feed"
    GRAPHITE_INSERTION = "2. Graphite core insertion"
    FERRULE_INSTALLATION = "3. Ferrule installation"
    ERASER_INSERTION = "4. Eraser insertion"
    QUALITY_INSPECTION = "5. Final quality inspection"
    SORTING = "6. Sorting and discharge"


STAGE_SEQUENCE: tuple[Stage, ...] = (
    Stage.BODY_FEED,
    Stage.GRAPHITE_INSERTION,
    Stage.FERRULE_INSTALLATION,
    Stage.ERASER_INSERTION,
    Stage.QUALITY_INSPECTION,
    Stage.SORTING,
)


@dataclass(slots=True)
class ProductRecord:
    product_id: int
    result: str
    defect_reason: str
    cycle_time_s: float
    completed_at: str
    measurements: dict[str, float | str | bool] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class ProductionSnapshot:
    state: MachineState = MachineState.IDLE
    stage: Stage = Stage.WAITING
    stage_index: int = -1
    total_count: int = 0
    good_count: int = 0
    defect_count: int = 0
    temperature_c: float = 24.0
    last_cycle_time_s: float = 0.0
    current_product_id: int | None = None
    last_defect_reason: str = "None"
    fault_message: str = ""
    database_connected: bool = False
    target_cycle_s: float = 5.4
    defect_probability: float = 0.08
    machine_speed: float = 1.0
    yield_percent: float = 100.0
    event_log: list[dict[str, str]] = field(default_factory=list)
    recent_products: list[ProductRecord] = field(default_factory=list)
    uptime_s: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["state"] = self.state.value
        payload["stage"] = self.stage.value
        payload["recent_products"] = [p.to_dict() for p in self.recent_products]
        return payload
