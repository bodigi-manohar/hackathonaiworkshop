import numpy as np
import pandas as pd

from ml.data import load_levels
from ml.features import build_table, feature_columns, prepare_level
from ml.backtest import make_folds


def test_no_feature_uses_data_after_origin(cfg):
    lv = prepare_level(load_levels(cfg, rebuild=True)["portfolio"], cfg)
    o = 48 * 40
    a = build_table(lv, cfg, origins=np.array([o]))
    bad = lv.copy()
    bad.loc[o:, ["load_kw", "solar_kw", "net_load_kw"]] = 1e9      # destroy every value from the origin onward
    b = build_table(bad, cfg, origins=np.array([o]))
    cols = [c for c in feature_columns(a)]
    pd.testing.assert_frame_equal(a[cols], b[cols])
    assert not np.allclose(a["y_kw"], b["y_kw"])                    # the target did change, features did not


def test_lags_are_in_the_past(cfg):
    lv = prepare_level(load_levels(cfg)["portfolio"], cfg)
    o = 48 * 20
    t = build_table(lv, cfg, origins=np.array([o]))
    y = lv["load_kw"].to_numpy()
    assert np.isclose(t.loc[t.horizon == 47, "lag_d1"].iloc[0], y[o + 47 - 48])   # last horizon still looks at o-1
    assert np.isclose(t["last"].iloc[0], y[o - 1])


def test_walkforward_folds_never_overlap():
    for f in make_folds(300, 6, 30, 14):
        assert f["val_start"] < f["test_start"] < f["test_end"]
    assert make_folds(300, 6, 30, 14)[-1]["test_end"] == 300
