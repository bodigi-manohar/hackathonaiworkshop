"""Guardrails (FR-604/FR-605): hard limits every actuating plan must pass."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class GuardrailLimits:
    max_kw: float
    soc_min_kwh: float
    soc_max_kwh: float
    max_setpoint_change_kw: float


def check_plan(plan: dict, limits: GuardrailLimits) -> list[str]:
    violations: list[str] = []
    prev_power: float | None = None
    for slot in plan.get("slots", []):
        power = max(
            abs(float(slot.get("battery_charge_kw", 0.0))),
            abs(float(slot.get("battery_discharge_kw", 0.0))),
        )
        idx = slot.get("slot")
        if power > limits.max_kw + 1e-6:
            violations.append(f"slot {idx}: power {power:.1f} kW exceeds max {limits.max_kw:.1f} kW")
        soc = float(slot.get("soc_kwh", 0.0))
        if soc < limits.soc_min_kwh - 1e-6 or soc > limits.soc_max_kwh + 1e-6:
            violations.append(
                f"slot {idx}: SoC {soc:.1f} kWh outside [{limits.soc_min_kwh:.1f}, {limits.soc_max_kwh:.1f}]"
            )
        if prev_power is not None and abs(power - prev_power) > limits.max_setpoint_change_kw + 1e-6:
            violations.append(
                f"slot {idx}: setpoint change {abs(power - prev_power):.1f} kW exceeds "
                f"{limits.max_setpoint_change_kw:.1f} kW"
            )
        prev_power = power
    return violations
