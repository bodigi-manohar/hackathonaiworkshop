"""Alert engine (FR-4xx). Pure function: reads forecast/metrics/explain_context, emits contract-format alerts.

Alert types: peak, ramp, low_confidence, model_drift, heatwave.
Cooldown (FR-406): an alert of the same type + entity is suppressed while its window still
overlaps (within cooldown_hours) an already-raised alert; suppressed candidates are returned separately.
"""
from __future__ import annotations

from datetime import datetime, timedelta

from backend.config import AppConfig


def _parse(ts: str) -> datetime:
    return datetime.fromisoformat(ts)


def evaluate(
    forecast: dict,
    metrics: dict | None,
    context: dict | None,
    cfg: AppConfig,
    existing: list[dict] | None = None,
) -> tuple[list[dict], list[dict]]:
    """Return (new_alerts, suppressed_alerts) in contracts/sample alerts.json format."""
    alerts: list[dict] = []
    suppressed: list[dict] = []
    existing = existing or []

    points = forecast.get("points", [])
    if not points:
        return alerts, suppressed

    level = forecast.get("level", "portfolio")
    entity = str(forecast.get("entity_id", "all"))
    quantile = "p90" if cfg.peak_quantile == "p90" else "p50"
    values = [float(p.get(quantile, p.get("p50", 0.0)) or 0.0) for p in points]
    stamps = [_parse(p["timestamp"]) for p in points]
    slot_minutes = int(forecast.get("slot_minutes", 30))

    def add(atype: str, severity: str, ws: datetime, we: datetime, value: float, threshold: float, message: str) -> None:
        candidate = {
            "id": f"{atype}-{entity}-{ws:%Y%m%d%H%M}",
            "type": atype,
            "severity": severity,
            "level": level,
            "entity_id": entity,
            "window_start": ws.isoformat(),
            "window_end": we.isoformat(),
            "value": round(value, 2),
            "threshold": round(threshold, 2),
            "message": message,
        }
        pad = timedelta(hours=cfg.cooldown_hours)
        for e in existing:
            if e.get("type") != atype or e.get("entity_id") != entity:
                continue
            try:
                ew_start = _parse(e["window_start"])
                ew_end = _parse(e["window_end"])
            except (KeyError, ValueError):
                continue
            if ws <= ew_end + pad and we >= ew_start - pad:
                suppressed.append(candidate)
                return
        alerts.append(candidate)

    # peak
    i = max(range(len(values)), key=lambda k: values[k])
    if values[i] > cfg.peak_threshold_kw:
        severity = "critical" if values[i] >= cfg.peak_threshold_kw * cfg.critical_factor else "warn"
        add(
            "peak",
            severity,
            stamps[i] - timedelta(minutes=slot_minutes),
            stamps[i] + timedelta(minutes=slot_minutes),
            values[i],
            cfg.peak_threshold_kw,
            f"{quantile.upper()} load {values[i]:.1f} kW exceeds threshold {cfg.peak_threshold_kw:.1f} kW",
        )

    # ramp
    z = max(1, int(cfg.ramp_window_slots))
    if len(values) > z:
        best: tuple[float, int] | None = None
        for k in range(len(values) - z):
            diff = values[k + z] - values[k]
            if best is None or abs(diff) > abs(best[0]):
                best = (diff, k)
        if best is not None and abs(best[0]) > cfg.ramp_kw:
            k = best[1]
            add(
                "ramp",
                "warn",
                stamps[k],
                stamps[k + z],
                abs(best[0]),
                cfg.ramp_kw,
                f"Load changes {best[0]:+.1f} kW within {z} slots",
            )

    # low confidence at the peak slot
    p50_peak = float(points[i].get("p50", 0.0) or 0.0)
    band = float(points[i].get("p90", 0.0) or 0.0) - float(points[i].get("p10", 0.0) or 0.0)
    if p50_peak > 0 and band / p50_peak > cfg.low_confidence_band_fraction:
        add(
            "low_confidence",
            "warn",
            stamps[i],
            stamps[i],
            round(band / p50_peak, 3),
            cfg.low_confidence_band_fraction,
            f"P10-P90 band is {band / p50_peak:.0%} of P50 at the peak slot",
        )

    # model drift
    if metrics and metrics.get("drift_ratio") is not None:
        ratio = float(metrics["drift_ratio"])
        if ratio > cfg.drift_ratio_threshold:
            origin = _parse(forecast["origin_time"])
            add(
                "model_drift",
                "critical" if ratio > cfg.drift_ratio_threshold + 0.3 else "warn",
                origin,
                origin + timedelta(hours=24),
                ratio,
                cfg.drift_ratio_threshold,
                f"Live MAE is {ratio:.2f}x training MAE; retrain recommended",
            )

    # heatwave
    if context and context.get("weather"):
        temp = context["weather"].get("max_apparent_temp_c")
        if temp is not None and float(temp) >= cfg.heatwave_apparent_temp_c:
            origin = _parse(forecast["origin_time"])
            add(
                "heatwave",
                "critical",
                origin,
                origin + timedelta(hours=24),
                float(temp),
                cfg.heatwave_apparent_temp_c,
                f"Apparent temperature {float(temp):.0f} C above heatwave threshold {cfg.heatwave_apparent_temp_c:.0f} C",
            )

    return alerts, suppressed
