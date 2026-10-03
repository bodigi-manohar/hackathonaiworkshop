"""Alert engine unit tests on synthetic forecasts."""
from datetime import datetime, timedelta, timezone

from backend.config import get_app_config
from backend.alerts import evaluate

TZ = timezone(timedelta(hours=11))
ORIGIN = datetime(2013, 2, 15, 0, 0, tzinfo=TZ)


def make_forecast(values, p10=None, p90=None):
    points = []
    for i, v in enumerate(values):
        points.append(
            {
                "slot": i,
                "timestamp": (ORIGIN + timedelta(minutes=30 * i)).isoformat(),
                "p10": (p10[i] if p10 else v - 5),
                "p50": v,
                "p90": (p90[i] if p90 else v + 5),
            }
        )
    return {
        "run_id": "test",
        "origin_time": ORIGIN.isoformat(),
        "level": "portfolio",
        "entity_id": "all",
        "slot_minutes": 30,
        "points": points,
    }


def types(alerts):
    return {a["type"] for a in alerts}


def test_flat_forecast_no_peak_alert():
    cfg = get_app_config()
    fc = make_forecast([100.0] * 48)
    alerts, _ = evaluate(fc, None, None, cfg)
    assert "peak" not in types(alerts)


def test_high_peak_fires_peak_alert():
    cfg = get_app_config()
    values = [100.0] * 48
    values[36] = 185.0
    fc = make_forecast(values)
    alerts, _ = evaluate(fc, None, None, cfg)
    peak = [a for a in alerts if a["type"] == "peak"]
    assert len(peak) == 1
    assert peak[0]["severity"] == "warn"
    assert peak[0]["value"] == 185.0
    assert peak[0]["threshold"] == cfg.peak_threshold_kw


def test_critical_peak_severity():
    cfg = get_app_config()
    values = [100.0] * 48
    values[36] = cfg.peak_threshold_kw * cfg.critical_factor + 5
    fc = make_forecast(values)
    alerts, _ = evaluate(fc, None, None, cfg)
    peak = [a for a in alerts if a["type"] == "peak"][0]
    assert peak["severity"] == "critical"


def test_ramp_alert():
    cfg = get_app_config()
    values = [100.0] * 48
    for k in range(4):
        values[30 + k] = 100.0 + (k + 1) * 10  # +40 kW within 4 slots
    fc = make_forecast(values)
    alerts, _ = evaluate(fc, None, None, cfg)
    assert "ramp" in types(alerts)


def test_low_confidence_alert():
    cfg = get_app_config()
    values = [100.0] * 48
    values[36] = 180.0
    p10 = [40.0] * 48
    p90 = [240.0] * 48
    fc = make_forecast(values, p10=p10, p90=p90)
    alerts, _ = evaluate(fc, None, None, cfg)
    assert "low_confidence" in types(alerts)


def test_drift_alert():
    cfg = get_app_config()
    fc = make_forecast([100.0] * 48)
    alerts, _ = evaluate(fc, {"drift_ratio": 1.5}, None, cfg)
    assert "model_drift" in types(alerts)


def test_heatwave_alert():
    cfg = get_app_config()
    fc = make_forecast([100.0] * 48)
    context = {"weather": {"max_apparent_temp_c": 38.0}}
    alerts, _ = evaluate(fc, None, context, cfg)
    assert "heatwave" in types(alerts)


def test_cooldown_suppresses_duplicate_peak():
    from backend.config import AppConfig

    cfg = AppConfig({})
    cfg.peak_threshold_kw = 100.0
    cfg.ramp_kw = 10000.0  # isolate the peak rule
    values = [100.0] * 48
    values[36] = 185.0
    fc = make_forecast(values)
    first, _ = evaluate(fc, None, None, cfg)
    assert [a["type"] for a in first] == ["peak"]
    _, suppressed = evaluate(fc, None, None, cfg, existing=first)
    assert types(suppressed) == {"peak"}


def test_cooldown_allows_different_entity():
    cfg = get_app_config()
    values = [100.0] * 48
    values[36] = 185.0
    fc = make_forecast(values)
    fc2 = dict(fc, entity_id="2000", level="zone")
    first, _ = evaluate(fc, None, None, cfg)
    second, _ = evaluate(fc2, None, None, cfg, existing=first)
    assert "peak" in types(second)
