"""Time-of-use tariff pricing per 30-minute slot (values are illustrative assumptions)."""
from __future__ import annotations


def slot_hour(slot: int, slot_minutes: int = 30) -> float:
    return (slot * slot_minutes / 60.0) % 24.0


def price_at_slot(slot: int, tariff: dict) -> float:
    hour = slot_hour(slot, int(tariff.get("slot_minutes", 30)))
    for band in tariff.get("bands", []):
        start, end = float(band["start_hour"]), float(band["end_hour"])
        inside = (hour >= start and hour < end) if start <= end else (hour >= start or hour < end)
        if inside:
            return float(band["price_per_kwh"])
    return float(tariff.get("shoulder_price_per_kwh", 0.24))


def prices_for_slots(n: int, tariff: dict) -> list[float]:
    return [price_at_slot(t, tariff) for t in range(n)]
