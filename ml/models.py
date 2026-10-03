"""Step 5: Ridge + LightGBM (horizon-as-feature) + quantile models, simplex blend, conformal calibration.

Per level (portfolio / zone / house) one pooled model is trained on load scaled by each entity's mean
load in the TRAINING window (so houses of different size share a model). Everything is returned in kW.
P50 = non-negative blend of Ridge and LightGBM (weights on the simplex, learned on the validation fold).
P10/P90 = LightGBM quantile models, widened/narrowed by a split-conformal offset learned on the same
validation fold so that coverage lands near the target (80%).
"""
from __future__ import annotations

import warnings

import joblib
import lightgbm as lgb
import numpy as np
import pandas as pd
from scipy.optimize import minimize
from sklearn.linear_model import Ridge
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from .features import LOAD_SCALED, feature_columns

warnings.filterwarnings("ignore", message=".*eval_set.*deprecated.*")
warnings.filterwarnings("ignore", category=UserWarning, module="lightgbm")

MODEL_NAMES = ["seasonal_naive", "weekly_naive", "moving_average", "ridge", "lgbm", "ensemble"]


def simplex_weights(P: np.ndarray, y: np.ndarray) -> np.ndarray:
    """Non-negative weights summing to 1 that minimise squared error of P @ w."""
    k = P.shape[1]
    res = minimize(lambda w: np.mean((P @ w - y) ** 2), np.ones(k) / k, method="SLSQP",
                   bounds=[(0, 1)] * k, constraints=[{"type": "eq", "fun": lambda w: w.sum() - 1}])
    w = np.clip(res.x, 0, None)
    return w / w.sum()


class LevelModel:
    def __init__(self, cfg: dict, level: str):
        self.cfg, self.level = cfg, level

    # ---- data prep -------------------------------------------------------------------------------
    def _xy(self, df: pd.DataFrame):
        X = df[self.features].copy()
        sc = df["entity_id"].map(self.scale).to_numpy(float)
        for c in LOAD_SCALED:
            if c in X:
                X[c] = X[c].to_numpy(float) / sc
        return X, df["y_kw"].to_numpy(float) / sc, sc

    # ---- training --------------------------------------------------------------------------------
    def fit(self, train: pd.DataFrame, val: pd.DataFrame) -> "LevelModel":
        m, seed = self.cfg["model"], self.cfg["model"]["seed"]
        self.features = feature_columns(train)
        self.scale = train.groupby("entity_id")["y_kw"].mean().replace(0, 1.0).to_dict()
        self.train_origin_end = str(train["origin_day"].max().date())
        Xtr, ytr, _ = self._xy(train)
        Xva, yva, _ = self._xy(val)
        ok = Xtr.notna().all(axis=1).to_numpy() & np.isfinite(ytr)       # long-gap rows excluded
        okv = Xva.notna().all(axis=1).to_numpy() & np.isfinite(yva)
        Xtr, ytr, Xva, yva = Xtr[ok], ytr[ok], Xva[okv], yva[okv]
        self.medians = Xtr.median()
        cat = ["entity_code"] if "entity_code" in self.features else []
        lp = {k: v for k, v in m["lgbm"].items() if k != "early_stopping_rounds"}
        base = dict(**lp, random_state=seed, n_jobs=-1, verbose=-1)
        cb = lambda: [lgb.early_stopping(m["lgbm"]["early_stopping_rounds"], verbose=False)]
        fit_kw = dict(eval_set=[(Xva, yva)], categorical_feature=cat or "auto", callbacks=cb())
        self.m_mean = lgb.LGBMRegressor(objective="regression", **base).fit(Xtr, ytr, eval_metric="l1", **fit_kw)
        qlo, qhi = m["quantiles"]
        self.m_lo = lgb.LGBMRegressor(objective="quantile", alpha=qlo, **base).fit(Xtr, ytr, **dict(fit_kw, callbacks=cb()))
        self.m_hi = lgb.LGBMRegressor(objective="quantile", alpha=qhi, **base).fit(Xtr, ytr, **dict(fit_kw, callbacks=cb()))
        self.ridge = make_pipeline(StandardScaler(), Ridge(alpha=m["ridge_alpha"])).fit(Xtr.fillna(self.medians), ytr)
        # ---- validation fold: blend weights + conformal band offset
        r = self._raw(Xva)
        self.weights = simplex_weights(np.column_stack([r["ridge"], r["lgbm"]]), yva)
        lo, hi = np.minimum(r["lo"], r["hi"]), np.maximum(r["lo"], r["hi"])
        E = np.sort(np.maximum(lo - yva, yva - hi))
        n = len(E)
        self.q_adj = float(E[min(n - 1, int(np.ceil((n + 1) * m["interval_coverage"])) - 1)])
        self.val_rows = int(n)
        return self

    def _raw(self, X: pd.DataFrame) -> dict:
        return {"ridge": self.ridge.predict(X.fillna(self.medians)), "lgbm": self.m_mean.predict(X),
                "lo": self.m_lo.predict(X), "hi": self.m_hi.predict(X)}

    # ---- inference (kW) --------------------------------------------------------------------------
    def predict(self, df: pd.DataFrame) -> pd.DataFrame:
        X, _, sc = self._xy(df)
        r = self._raw(X)
        p50 = (self.weights[0] * r["ridge"] + self.weights[1] * r["lgbm"]) * sc
        lo = (np.minimum(r["lo"], r["hi"]) - self.q_adj) * sc
        hi = (np.maximum(r["lo"], r["hi"]) + self.q_adj) * sc
        p50 = np.clip(p50, 0, None)
        p10, p90 = np.clip(np.minimum(lo, p50), 0, None), np.maximum(hi, p50)
        return pd.DataFrame({"ridge": np.clip(r["ridge"] * sc, 0, None), "lgbm": np.clip(r["lgbm"] * sc, 0, None),
                             "ensemble": p50, "p10": p10, "p90": p90}, index=df.index)

    def save(self, p) -> None:
        joblib.dump(self, p)

    @staticmethod
    def load(p) -> "LevelModel":
        return joblib.load(p)


def baseline_forecast(df: pd.DataFrame) -> pd.DataFrame:
    """Seasonal-naive P50 (same slot yesterday) with +/-10% band. Used for the first contract file."""
    p50 = df["naive_d1"].to_numpy(float)
    return pd.DataFrame({"ensemble": p50, "p10": p50 * 0.9, "p90": p50 * 1.1}, index=df.index)
