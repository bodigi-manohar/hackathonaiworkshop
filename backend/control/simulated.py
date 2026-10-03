"""In-memory simulated battery (FR-602)."""
from __future__ import annotations

from backend.control.adapter import ControlAdapter


class SimulatedBatteryAdapter(ControlAdapter):
    name = "simulated"

    def __init__(self, soc_initial_kwh: float = 0.0, max_kw: float = float("inf")):
        self.soc_kwh = float(soc_initial_kwh)
        self.max_kw = float(max_kw)
        self.commands: list[dict] = []
        self._snapshots: list[float] = []

    def read_state(self) -> dict:
        return {
            "adapter": self.name,
            "soc_kwh": round(self.soc_kwh, 2),
            "commands_applied": len(self.commands),
        }

    def apply_setpoints(self, plan: dict) -> dict:
        if any(
            max(abs(float(s.get("battery_charge_kw", 0.0))), abs(float(s.get("battery_discharge_kw", 0.0))))
            > self.max_kw + 1e-6
            for s in plan.get("slots", [])
        ):
            raise ValueError(f"plan exceeds simulated battery max power {self.max_kw} kW")
        self._snapshots.append(self.soc_kwh)
        for slot in plan.get("slots", []):
            charge = float(slot.get("battery_charge_kw", 0.0))
            discharge = float(slot.get("battery_discharge_kw", 0.0))
            self.soc_kwh += 0.5 * (charge - discharge)
            self.commands.append(
                {"slot": slot.get("slot"), "charge_kw": charge, "discharge_kw": discharge}
            )
        return {"applied": True, **self.read_state()}

    def rollback(self) -> dict:
        if self._snapshots:
            self.soc_kwh = self._snapshots.pop()
            self.commands.clear()
            return {"rolled_back": True, **self.read_state()}
        return {"rolled_back": False, **self.read_state()}
