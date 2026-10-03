"""Deferrable load shifting (FR-504): place a load in the cheapest feasible window."""
from __future__ import annotations


def cheapest_window(
    prices: list[float],
    duration_slots: int,
    allowed_start_slot: int,
    allowed_end_slot: int,
) -> int | None:
    """Start slot of the cheapest consecutive window; None if no feasible window."""
    if duration_slots <= 0:
        return None
    n = len(prices)
    start = max(0, allowed_start_slot)
    end = min(n - 1, allowed_end_slot)
    if end - start + 1 < duration_slots:
        return None
    best_start: int | None = None
    best_cost: float | None = None
    for s in range(start, end - duration_slots + 2):
        cost = sum(prices[s : s + duration_slots])
        if best_cost is None or cost < best_cost:
            best_cost = cost
            best_start = s
    return best_start
