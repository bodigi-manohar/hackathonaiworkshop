import numpy as np

from ml.data import aggregate, load_raw, tidy_houses


def test_sum_of_houses_equals_zone_equals_portfolio(cfg):
    houses, qc = tidy_houses(load_raw(cfg), cfg)
    zone, port = aggregate(houses, cfg)
    complete = houses.groupby("timestamp")["load_kw"].apply(lambda s: s.notna().all())
    ts = complete[complete].index[:500]
    h = houses[houses.timestamp.isin(ts)]
    z = zone[zone.timestamp.isin(ts)]
    p = port[port.timestamp.isin(ts)]
    assert np.allclose(h.groupby("timestamp")["load_kw"].sum().to_numpy(), p.sort_values("timestamp")["load_kw"].to_numpy())
    assert np.allclose(z.groupby("timestamp")["load_kw"].sum().to_numpy(), p.sort_values("timestamp")["load_kw"].to_numpy())
    assert qc["totals"]["missing_slots"] > 0          # synthetic gaps were detected


def test_no_partial_sums(cfg):
    houses, _ = tidy_houses(load_raw(cfg), cfg)
    _, port = aggregate(houses, cfg)
    bad = houses.groupby("timestamp")["load_kw"].apply(lambda s: s.isna().any())
    nan_ts = bad[bad].index
    assert port[port.timestamp.isin(nan_ts)]["load_kw"].isna().all()
