"""Control adapter interface (FR-601)."""
from __future__ import annotations

from abc import ABC, abstractmethod


class ControlAdapter(ABC):
    name: str = "base"

    @abstractmethod
    def read_state(self) -> dict: ...

    @abstractmethod
    def apply_setpoints(self, plan: dict) -> dict: ...

    def rollback(self) -> dict:
        return {"rolled_back": False, "adapter": self.name}
