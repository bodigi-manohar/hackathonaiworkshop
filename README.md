# GridSight — Short-Term Energy Demand Forecasting Agent

Problem 27: energy demand forecasting for utilities. The system forecasts the next 24 hours
(48 half-hour slots) of electricity demand at **portfolio / zone / house** level with
P10–P50–P90 uncertainty bands, backed by a walk-forward validated ensemble. Everything is
advisory only — the LLM explains pre-computed results and never calculates numbers.

## Team layout

| Folder | Owner | Contents |
|---|---|---|
| `ml/` | Member 1 (Manohar) | data ingest + QC, features, LightGBM/Ridge/ensemble, backtest, run bundles |
| `backend/` | Member 2 | FastAPI + alerts + optimizer + chat (serves `runs/<run_id>/`) |
| `frontend/` | Member 3 | dashboard |
| `contracts/sample/` | shared | agreed JSON contracts (forecast, alerts, plan, metrics, explain_context, entities) |
| `docs/` | shared | PRD, Member-1 role doc, generated data schema + results |

## Member 1 (`ml/`) quick start

```bash
pip install -r requirements.txt

# point at the raw data (or put the CSV under data/raw/)
export GRIDSIGHT_RAW_CSV=/path/to/Ausgrid_Community_Final.csv

python -m ml.data                                  # tidy parquet + QC report + docs/DATA_SCHEMA.md
python -m pytest ml/tests -q                       # leakage, aggregation, contract tests
python -m ml.backtest                              # walk-forward -> reports/, docs/RESULTS.md, results.xlsx
python -m ml.train --train-end 2013-02-01          # final models (origins on/after this day are out-of-sample)
python -m ml.run_cycle --origin 2013-02-15T00:00   # full run bundle in runs/<run_id>/

# faster while iterating:
python -m ml.backtest --levels portfolio,zone
```

**Weather note:** the Kaggle dataset's weather columns are mislabeled (e.g. `T2M` actually held
radiation). `ml/data.py` now detects implausible ranges and rebuilds
`T2M/QV2M/PS/WS10M/T2MWET/PRECTOTCORR` from the Open-Meteo archive for Sydney (cached under
`data/cache/weather/`), so features, accuracy and the explain context stay honest.

## Verified results (walk-forward, oracle weather)

| Level | Ensemble MAE | Skill vs seasonal-naive | P10–P90 coverage |
|---|---|---|---|
| Portfolio | 18.79 kW | 0.280 | 77.5% |
| Zone | 2.98 kW | 0.248 | 78.9% |
| House | 1.79 kW | 0.236 | 79.3% |

Full tables: `reports/backtest.md`, `reports/results.xlsx`, `docs/RESULTS.md`.
With degraded (noisy) weather the portfolio skill is 0.208 — the expected degradation.

## Run bundle (what Members 2 & 3 consume)

`runs/<run_id>/`: `forecast.json` (portfolio), `forecast_zone_*.json`, `forecast_house_*.json`,
`explain_context.json`, `metrics.json`, `run_meta.json`, `entities.json`.
48 points, unit kW, `p10 <= p50 <= p90`, timestamps in Australia/Sydney, one slot = 30 min.

## Rules

- Walk-forward (expanding window) only — never shuffled k-fold, never fit on future data.
- Use the word **house**, never "community".
- Outputs are advisory only.
- The LLM only explains pre-computed results (`explain_context.json`).