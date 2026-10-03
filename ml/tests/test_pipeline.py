import json

import numpy as np

from ml.backtest import run_backtest
from ml.run_cycle import run_cycle, validate_forecast
from ml.train import train_final
from ml.config import path


def _load(cfg, run_id, name):
    return json.loads((path(cfg, "runs_dir", run_id) / name).read_text())


def test_baseline_bundle_matches_contract(cfg):
    rid = run_cycle(cfg, "2012-11-05T00:00", model="baseline", force=True)
    fc = _load(cfg, rid, "forecast.json")
    validate_forecast(fc)
    assert fc["origin_time"].startswith("2012-11-05T00:00:00+11:00")     # AEDT after the first Sunday of October
    assert len(fc["history"]) == 48 and len({p["slot"] for p in fc["points"]}) == 48
    # plausible daily shape: evening above overnight
    p50 = np.array([p["p50"] for p in fc["points"]])
    assert p50[34:42].mean() > p50[4:10].mean()


def test_backtest_train_and_ensemble_bundle(cfg):
    m = run_backtest(cfg, ["portfolio", "zone", "house"])
    bm = {r["model"]: r for r in m["by_model"]}
    assert bm["ensemble"]["mae"] < bm["seasonal_naive"]["mae"], "ensemble must beat seasonal naive"
    assert 0.5 < m["coverage_p10_p90"] <= 1.0
    train_final(cfg)
    rid = run_cycle(cfg, "2012-11-05T00:00", model="ensemble", force=True)
    for name in ("forecast.json", "metrics.json", "explain_context.json", "entities.json", "run_meta.json", "forecast_zone_Cluster_0.json", "forecast_house_1.json"):
        assert (path(cfg, "runs_dir", rid) / name).exists(), name
    for name in ("forecast.json", "forecast_zone_Cluster_0.json", "forecast_house_1.json"):
        validate_forecast(_load(cfg, rid, name))
    ctx = _load(cfg, rid, "explain_context.json")
    assert ctx["total_kwh_next_24h"] > 0 and ctx["peak"]["p50_kw"] > 0 and 1 <= len(ctx["drivers"]) <= 3
    assert _load(cfg, rid, "run_meta.json")["in_sample"] is False
