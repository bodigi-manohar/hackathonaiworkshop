"""BACnet stub (FR-602): only logs what it would send; never actuates."""
from __future__ import annotations

import logging

from backend.control.adapter import ControlAdapter

logger = logging.getLogger("gridsight.control.bacnet")


class BACnetAdapterStub(ControlAdapter):
    name = "bacnet_stub"

    def __init__(self):
        self.would_send: list[dict] = []

    def read_state(self) -> dict:
        return {"adapter": self.name, "logged_setpoints": len(self.would_send)}

    def apply_setpoints(self, plan: dict) -> dict:
        for slot in plan.get("slots", []):
            entry = {
                "slot": slot.get("slot"),
                "charge_kw": slot.get("battery_charge_kw", 0.0),
                "discharge_kw": slot.get("battery_discharge_kw", 0.0),
            }
            self.would_send.append(entry)
            logger.info("[bacnet-stub] would send: %s", entry)
        return {"applied": False, "stub": True, **self.read_state()}
