# PRD — GridSight: Short-Term Energy Demand Forecasting Agent

**Version:** 1.1 | **Date:** 2026-10-03 | **Owner:** Manohar
**Source problem:** Problem 27 — Energy demand forecasting for utilities (Energy/Utilities)
**Build environment:** OpenCode (coding agent) with API key
**Status:** Ready to build

> **v1.0 → v1.1 changes (cross-check fixes):** defined `make demo` (§9.5); added `run.py` CLI to repo layout (§9.1); run bundles now keyed on `origin_time` + run id (FR-303); FR-202 fixed to horizon-as-feature; P50 fixed to ensemble median (FR-205); FR-206 split into 24h (M3) and FR-206a 7-day peaks (M8); default `origin_time` specified (§9.5); battery `soc_initial_kwh` added (FR-501); demand-charge peak variable added to LP spec (FR-502); negative-saving plans forbidden (FR-506); alert cooldown added (FR-406); timezone pinned to `Australia/Sydney` (§4.1); zone fallback defined (§4.2); `POST /run` idempotency defined (FR-801); inputs hash pinned to `run.log` (FR-303); noisy-weather σ moved to config (§7.2); path-from-config rule added (§6); dataset years settled at M0 (§4.1).

---

## 0. How to use this document in OpenCode

1. Create an empty repo folder, open it in OpenCode.
2. Save this file as `docs/PRD.md`. Copy **Section 17 (AGENTS.md)** into `AGENTS.md` at the repo root so OpenCode keeps the rules in context.
3. Build **one milestone at a time** (Section 15). For each milestone paste the prompt given there, let OpenCode finish, run the acceptance check, commit, then go to the next.
4. Do not ask OpenCode to "build everything" in one shot. The milestones are ordered so that something demo-able exists after M3.

---

## 1. Overview

### 1.1 Problem
Grid operators, retailers and large facility managers must match supply and demand continuously. Over-forecasting wastes fuel and standby capacity; under-forecasting causes expensive spot purchases or blackouts. Existing practice relies on ARIMA/regression models with historical averages, lacks granularity (zone, consumer type), and cannot react to real-time events such as heatwaves. Renewable output (solar/wind) adds variability. Demand-side flexibility is mostly manual.

### 1.2 Product vision
**GridSight** is a forecasting agent that, every cycle (hourly or daily), ingests recent consumption + weather + calendar data, produces tight multi-horizon demand forecasts with uncertainty bands at several granularity levels, raises peak alerts, recommends cost-saving load-shifting / battery actions, and explains everything in plain language. All actions are advisory unless an operator explicitly enables bounded automation.

### 1.3 Why this fits our existing work
We already have the Ausgrid residential dataset pipeline, a LightGBM + Ridge ensemble, an Embedding-MLP and CNN-BiLSTM-attention models, a walk-forward validation discipline, an HTML tab dashboard, and an LLM layer that only explains pre-computed results. GridSight **reuses** these ideas and extends them from "one household forecast" to "zone/portfolio forecast + decision support".

### 1.4 Goals
| ID | Goal |
|----|------|
| G1 | Produce a next-24h demand forecast (48 half-hour slots) at house, zone and portfolio level |
| G2 | Beat a seasonal-naive baseline by a clear margin (target ≥ 15% lower MAE at portfolio level) |
| G3 | Provide P10/P50/P90 uncertainty bands so reserve decisions can be made |
| G4 | Detect and alert on forecast peaks above a configurable threshold |
| G5 | Recommend load-shifting / battery dispatch under a time-of-use tariff and show the estimated saving |
| G6 | Offer a dashboard and a chat interface that explains forecasts without recalculating them |
| G7 | Keep a human in the loop: advisory by default, bounded, logged, overridable |

### 1.5 Non-goals (v1)
- No real SCADA, smart-meter or BACnet connection (only simulated adapters with a clean interface).
- No live wholesale-market trading (use a static / mocked price feed).
- No wind-farm output forecasting (solar is covered via the dataset's generation columns).
- No multi-user auth or multi-tenant SaaS features.
- No self-hosted SLM fine-tuning in this build (the LLM is an external API behind an adapter, swappable later).
- No 7-day daily-peak forecasting until M8 (kept out of the MVP/v1 core on purpose).

---

## 2. Users and use cases

| Persona | Need | Key use case |
|---------|------|--------------|
| **Grid / zone operator** | Know tomorrow's load and peak risk | View 24h zone forecast with P10–P90 band, get peak alert |
| **Energy retailer** | Buy power ahead at lower cost | Export forecast CSV/JSON for procurement |
| **Facility / campus manager** | Smooth peaks, cut bills | See battery / load-shift plan and projected saving |
| **Microgrid operator** | Balance local solar and demand | Net-load (demand minus solar) forecast |
| **Evaluator / professor** | Trust and reproducibility | Metrics report, walk-forward results, explainable outputs |

---

## 3. Scope by phase

| Phase | Name | Contents |
|-------|------|----------|
| **MVP** | Forecast engine | Data ingest, features, baselines, LightGBM+Ridge forecast, CSV of next 24h, metrics report (matches the problem statement's MVP) |
| **v1** | Agent + decision support | Uncertainty bands, multi-level granularity, scheduler, alerts, load-shift/battery optimizer, FastAPI, dashboard, LLM explainer chat |
| **v1.5 (stretch)** | Model depth | Embedding-MLP and CNN-BiLSTM-attention models added to the ensemble, TimesFM-style foundation model as an optional extra, drift monitoring and auto-retrain trigger, 7-day daily-peak forecast |

**Build target for today: MVP + as much of v1 as time allows, in milestone order.**

---

## 4. Data

### 4.1 Primary dataset
Ausgrid Solar Home Electricity Data (300 households, 30-minute intervals, ~3 years; the M0 audit in §15 pins the exact date range — do not assume). Typical raw layout: one row per customer per day, with 48 wide columns per consumption category. Categories: **GC** (general consumption), **CL** (controlled load), **GG** (gross generation / solar). Row count after expansion is ≈ 300 × days × 48 (~15–16 M rows) — fine for parquet.

> **Phase-0 task for OpenCode:** inspect the actual files in `data/raw/` (or the processed parquet/CSV from the previous project) and write down the real schema, date range, and category layout in `docs/DATA_SCHEMA.md` before coding anything. Do not assume the layout above is exact.

### 4.2 Derived series
- `load_kw` = GC + CL per house per slot (kWh per 30 min × 2 → kW).
- `solar_kw` = GG per slot.
- `net_load_kw` = `load_kw` − `solar_kw`.
- Aggregations: **house** (one customer), **zone** (group by postcode, configurable), **portfolio** (all houses).
- **Zone fallback:** if no postcode mapping exists for some houses, group by the next available geographic field (e.g. DivID); if none exists, those houses belong to a single zone `ALL` with a `zone_source="unmapped"` flag. Never silently drop houses from a zone.
- Naming rule: use the word **house** everywhere. Never use "community" in code, columns, docs or UI.

### 4.3 Weather
- Source: Open-Meteo (free, no API key) — historical archive for training, forecast endpoint for live runs. Location: Sydney region matching the dataset postcodes; default lat/lon in `config.yaml` (e.g. `-33.87, 151.21`), overridable.
- Variables: temperature_2m, relative_humidity_2m, apparent_temperature, cloud_cover, shortwave_radiation, wind_speed_10m, precipitation.
- Cache all responses to `data/cache/weather/` as parquet; the pipeline must work **offline from cache** (fallback for poor connectivity).
- If the sandbox has no network access, provide a synthetic-weather fallback derived from the dataset's own solar generation and a clearly flagged `weather_source="synthetic"` column. Never silently fake weather.

### 4.4 Calendar features
Hour/slot of day, day of week, weekend flag, public holidays (NSW; use the `holidays` package), month, season, school-holiday flag (static file, optional).

### 4.5 Tariff and battery config (simulated)
`config.yaml` holds a time-of-use tariff, for example: off-peak (10pm–7am), shoulder, peak (2pm–8pm) with currency per kWh, plus an optional demand charge per kW. Treat the values as **assumptions**, label them as such in the UI and report.

### 4.6 Data quality rules
- Detect missing slots, duplicates, DST changes, negative values and outliers; log counts to `reports/data_quality.json`.
- Impute short gaps (≤ 3 slots) by interpolation; longer gaps flagged and excluded from training windows.
- Time zone: **all internal storage is UTC** (tz-aware, `tz=UTC`). Display uses **`Australia/Sydney`** (AEST/AEDT — DST shifts fall inside the data period, so every parse must be tz-aware and every conversion explicit). All timestamps in config, CLI and API are local `Australia/Sydney` unless suffixed with `Z`.

---

## 5. Functional requirements

### 5.1 Ingestion and features (FR-1xx)
| ID | Requirement |
|----|-------------|
| FR-101 | Load raw Ausgrid files into a tidy long-format table `(timestamp, house_id, zone_id, load_kw, solar_kw, net_load_kw)` stored as parquet |
| FR-102 | Build aggregates at zone and portfolio level |
| FR-103 | Fetch + cache weather; join on timestamp (hourly weather forward-filled to 30-min) |
| FR-104 | Feature builder with: lags (1, 2, 48, 96, 336 slots), rolling mean/std (6, 48, 336), calendar features, weather features, weather lags, solar-position proxy (hour-angle features), lagged solar |
| FR-105 | **Leakage guard:** a unit test asserts no feature at time *t* uses data after *t* (forecast origin discipline). Weather forecast features may use only forecast values available at origin time (in backtests, use actuals but label them "oracle weather"; also report a degraded-weather run with noise added) |

### 5.2 Forecasting (FR-2xx)
| ID | Requirement |
|----|-------------|
| FR-201 | Baselines: seasonal-naive (same slot yesterday), weekly-naive (same slot last week), and moving-average |
| FR-202 | Primary model: **LightGBM, horizon-as-feature** — a single regression model with `horizon_slot` (1..48) as a feature, plus dedicated quantile models (FR-205). One-per-horizon-model is a documented alternative, off by default |
| FR-203 | Secondary model: **Ridge** on the same features |
| FR-204 | Ensemble: weighted blend, weights learned on a validation fold by projecting onto the probability simplex (non-negative, sum to 1; e.g. `scipy.optimize.minimize` SLSQP or explicit simplex projection) |
| FR-205 | Quantile forecasts: LightGBM quantile objective for P10 and P90; **P50 = median of the ensemble predictions** (robust to outliers, consistent with quantile semantics) |
| FR-206 | Forecast horizons: 24h ahead at 30-min resolution (default) plus an hourly roll-up. **Milestone M3** |
| FR-206a | 7-day daily-peak forecast (max-load slot per day). **Milestone M8 / stretch only** |
| FR-207 | Validation: **walk-forward (expanding window) only**. K-fold with shuffling is forbidden (it leaked in our earlier experiments) |
| FR-208 | Models are serialized to `models/` with metadata (train window, features, metrics, git hash) |
| FR-209 | (v1.5) Embedding-MLP: 5-day input window to predict the next day, with slot/day-of-week embeddings |
| FR-210 | (v1.5) CNN-BiLSTM with attention as an additional ensemble member |
| FR-211 | (v1.5) Optional foundation-model adapter (TimesFM-style) behind the same `Forecaster` interface, zero-shot, compared in the report |

### 5.3 Agent orchestration (FR-3xx)
The "agent" is a **deterministic tool-calling pipeline** with an LLM used only for explanation and natural-language queries. Numeric work is never done by the LLM.

| ID | Requirement |
|----|-------------|
| FR-301 | `run_cycle(origin_time)` executes: ingest latest data → build features → forecast → quantiles → alerts → optimizer → persist results → write audit log |
| FR-302 | Scheduler: nightly full run (default 00:00 local) and optional hourly refresh using the newest available data; CLI and API triggers also supported |
| FR-303 | Each run produces a **run bundle** in `runs/<origin_time-utc-slug>_<run_id>/` (keyed on origin, not wall-clock, so replayed runs never collide): `forecast.csv`, `forecast.json`, `alerts.json`, `plan.json`, `metrics.json`, `explain_context.json`, `run.log`. `run.log` (structured JSON lines) records the **inputs hash** (SHA-256 of the input data slice + weather cache manifest), model version, config version, trigger, and per-stage timings |
| FR-304 | Event handling: if a heatwave flag (apparent temperature above a configurable threshold) appears in the weather forecast, trigger an out-of-cycle re-forecast and tag the run `event=heatwave` |
| FR-305 | Self-refinement: after actuals arrive, compute realized error, append to `data/feedback/error_log.parquet`; weekly retrain job uses the newest data (walk-forward) |
| FR-306 | Drift monitor: rolling 7-day MAE vs. training MAE; if ratio > configurable threshold (default 1.3), raise a `model_drift` alert and flag for retraining |

### 5.4 Alerts (FR-4xx)
| ID | Requirement |
|----|-------------|
| FR-401 | Peak alert: forecast P50 (or P90, configurable) above threshold X kW for a zone/portfolio within the next 24h |
| FR-402 | Ramp alert: change greater than Y kW within Z slots (e.g. evening ramp as solar drops) |
| FR-403 | Low-confidence alert: P90–P10 band wider than a configurable fraction of P50 |
| FR-404 | Alerts delivered to: JSON file, dashboard panel, optional webhook (Slack-style URL in env var; off by default) |
| FR-405 | Every alert has severity (info/warn/critical), reason, time window, and the numbers behind it |
| FR-406 | **Cooldown / dedup:** an alert of the same type for the same entity is suppressed while its forecast window (or a configurable cooldown, default 6h) still overlaps an already-raised alert; re-raise is logged, not duplicated |

### 5.5 Load-shifting and battery optimizer (FR-5xx)
| ID | Requirement |
|----|-------------|
| FR-501 | Inputs: net-load forecast (P50, plus P90 for a conservative mode), tariff schedule, battery spec (capacity kWh, max charge/discharge kW, round-trip efficiency, min/max SoC, **initial SoC `soc_initial_kwh`** at cycle start), optional demand-charge rate |
| FR-502 | Solver: linear program (`scipy.optimize.linprog` or `pulp`) minimizing energy cost + demand charge, over 48 slots, with SoC dynamics and limits. **Demand charge is linearized with an auxiliary peak-import variable** `p` and constraints `p ≥ grid_import_slot` for all slots (cost term `p × demand_charge`). Fall back to a greedy rule if the solver fails |
| FR-503 | Output: per-slot charge/discharge schedule, resulting grid import profile, **before vs. after** cost, peak reduction (kW and %), and a plain-language summary seed for the LLM |
| FR-504 | Flexible-load shifting: given a list of deferrable loads (name, kW, duration, allowed window), place them in the cheapest feasible window |
| FR-505 | A "generator vs. grid" recommendation: compare marginal grid price per slot against a configurable generator cost and flag slots where running the generator is cheaper |
| FR-506 | **Never emit a negative-saving plan:** the optimizer always compares against do-nothing; if the best plan costs more, emit an empty advisory plan with `saving: 0` and a note. All output is a **recommendation** (`mode=advisory`). Nothing is executed unless the control adapter is enabled (Section 5.6) |

### 5.6 Control adapter (FR-6xx) — simulated
| ID | Requirement |
|----|-------------|
| FR-601 | Abstract `ControlAdapter` interface: `read_state()`, `apply_setpoints(plan)`, `rollback()` |
| FR-602 | Provide `SimulatedBatteryAdapter` (in-memory SoC model) and a `BACnetAdapterStub` that only logs what it would send |
| FR-603 | Default config: `control.enabled: false`, `dry_run: true` |
| FR-604 | Guardrails when enabled: operator-set hard limits (max kW, SoC bounds, max setpoint change per interval), every command logged with before/after state, and a one-call manual override that disables control immediately |
| FR-605 | Any plan violating a guardrail is rejected and an alert raised |

### 5.7 LLM explainer (FR-7xx)
| ID | Requirement |
|----|-------------|
| FR-701 | A provider-agnostic `LLMClient` using an OpenAI-compatible chat endpoint. Provider, base URL, model name and key come from environment variables, so the OpenCode-provided key and model can be dropped in without code changes |
| FR-702 | The LLM receives **only** `explain_context.json` and the user's question (retrieval-then-explain). It must never compute or alter forecasts. System prompt enforces: answer only from the provided context, cite the numbers used, say "not in the data" otherwise |
| FR-703 | Supported questions: "Why is the evening peak high?", "What is the biggest risk tomorrow?", "How much does the battery plan save?", "How accurate was yesterday's forecast?", "Summarize this run for the operator" |
| FR-704 | A deterministic template-based fallback summary is used when the LLM is unavailable (so the demo never breaks) |
| FR-705 | Prompt-injection hygiene: user text is treated as a question only; data fields are passed as structured JSON; the LLM has no tools that mutate state |

### 5.8 API (FR-8xx) — FastAPI
| Method | Path | Purpose |
|--------|------|---------|
| GET | `/health` | Liveness and version |
| GET | `/forecast?level=portfolio\|zone\|house&id=...&horizon=24h` | Latest forecast with bands |
| GET | `/forecast/csv` | Download next-24h CSV of the latest run bundle (the MVP deliverable, exposed via API in v1) |
| GET | `/alerts` | Active and recent alerts |
| GET | `/plan` | Latest battery / load-shift plan with cost comparison |
| POST | `/run` | Trigger a cycle manually (optionally with `origin_time`) |
| GET | `/metrics` | Backtest and live accuracy metrics |
| GET | `/runs` | List run bundles |
| POST | `/chat` | `{question, run_id?}` → grounded explanation |
| POST | `/control/override` | Immediately disable automation |

All responses are typed with Pydantic models; OpenAPI docs available at `/docs`.

| ID | Requirement |
|----|-------------|
| FR-801 | **Idempotency:** `POST /run` with the same `origin_time` returns the existing bundle (HTTP 200 + `run_id`) instead of re-running; add `force: true` to re-run and overwrite |

### 5.9 Dashboard (FR-9xx)
Single-page HTML + vanilla JS (or a small framework-free bundle) served by FastAPI, tab-switched in the same style as our earlier dashboard.

| Tab | Content |
|-----|---------|
| **Overview** | KPI cards (next-24h peak kW and time, total kWh, forecast MAPE last 7 days, active alerts), main chart with actuals (history), P50 line and P10–P90 band |
| **Granularity** | Selector for portfolio / zone / house; compare levels |
| **Alerts** | Table with severity, window, reason |
| **Optimizer** | Before/after grid import chart, battery SoC curve, cost saving, peak reduction, tariff bands shaded |
| **Accuracy** | Backtest table (models vs. baselines), error by hour of day, error by day of week, residual plot |
| **Assistant** | Chat box bound to `/chat`, with a banner "Answers use pre-computed results only" |
| **Settings** | Thresholds, tariff, battery spec (read-only display of `config.yaml` in v1) |

UI requirements: responsive, readable axis labels with units, colour-blind-safe palette, a visible "advisory only" badge, loading and error states, local time shown with timezone.

---

## 6. Non-functional requirements

| Area | Requirement |
|------|-------------|
| Performance | Portfolio-level forecast cycle ≤ 60 s on a laptop CPU; house-level for all 300 houses ≤ 10 min (batch, vectorized); API responses ≤ 500 ms from cached run bundles |
| Reproducibility | Fixed seeds, pinned `requirements.txt` (CPU wheels), `make` targets, deterministic splits, config in one `config.yaml`. **All filesystem paths come from `config.yaml`, relative to the project root — no hardcoded local paths anywhere, so training scripts also run on Kaggle** |
| Reliability | Pipeline works offline from caches; each stage fails loudly with a clear message; partial results are never published as complete |
| Observability | Structured JSON logs, run bundle audit trail, timing per stage |
| Security | No secrets in the repo; `.env.example` provided; `.env` git-ignored; CORS restricted to localhost by default |
| Testing | pytest with: leakage test, feature-shape test, metric-function tests, optimizer feasibility tests (SoC bounds respected, energy balance holds, `saving ≥ 0`), API smoke tests |
| Code quality | Type hints, ruff formatting, modules under 300 lines where practical, docstrings on public functions |
| Hardware | Assume CPU-only. Optional GPU for the v1.5 deep models |

---

## 7. Modeling specification

### 7.1 Targets
Primary target: `load_kw` at each level. Secondary (microgrid view): `net_load_kw`. Solar generation forecast as an auxiliary series if time permits.

### 7.2 Backtest protocol
- Expanding-window walk-forward with at least 6 monthly folds on the final year(s) of data; test origin each day at 00:00 predicting the next 48 slots.
- Report per fold and averaged.
- Compare: seasonal-naive, weekly-naive, Ridge, LightGBM, Ensemble (and v1.5 models).
- Weather scenarios: (a) oracle actual weather, (b) noisy weather — Gaussian noise on temperature and shortwave radiation with σ from `config.yaml` (`weather.backtest_noise: {temp_c: 2.0, radiation_w_m2: 50.0}`, seeded) to mimic real forecast error.

### 7.3 Metrics
| Metric | Notes |
|--------|-------|
| MAE, RMSE (kW) | Absolute error |
| nMAE / CV-RMSE | Normalized by mean load, comparable across levels |
| MAPE / sMAPE | Report sMAPE for house level where load can be near zero |
| Peak error | Error in the daily maximum (kW) and in peak timing (slots) |
| Skill score | `1 − MAE_model / MAE_seasonal_naive` |
| Coverage | Share of actuals inside P10–P90 (target ≈ 80%) |
| Pinball loss | For quantile quality |
| Decision metrics | Optimizer saving vs. no-battery baseline; peak kW reduction |

Targets (indicative, to be confirmed against the real data): portfolio-level nMAE below 8%; skill score ≥ 0.15 over seasonal-naive; coverage 75–85%. House-level error will be much larger because individual load is noisy; report it honestly instead of tuning to hide it.

### 7.4 Known pitfalls to design around
- **Zero-solar nighttime rows (~58% of rows):** do not let them distort solar metrics; compute solar metrics on daylight slots only and state this.
- **Temporal synchronization:** supply and demand peaks do not coincide, which limits any local matching. For the optimizer this is exactly why storage and shifting matter; mention it in the report.
- **Staircase artifacts from slot-expansion bugs (24→48):** add a test that the forecast has 48 distinct slot indices and a plausible daily shape.
- **Data leakage:** walk-forward only, enforced by tests.

---

## 8. Agent workflow (per cycle)

```
trigger (schedule | API | event)
  → 1. ingest newest meter data (or replay from dataset at origin_time)
  → 2. fetch weather forecast (cache fallback)
  → 3. build features at origin time (leakage-safe)
  → 4. forecast P10/P50/P90 for house, zone, portfolio
  → 5. evaluate alerts (peak, ramp, confidence, drift, heatwave; cooldown applied)
  → 6. run optimizer (battery + shiftable loads + generator check)
  → 7. validate plan against guardrails (never emit negative-saving plan)
  → 8. persist run bundle + audit log (inputs hash, model + config version)
  → 9. (optional) apply via ControlAdapter if enabled and not dry-run
  → 10. build explain_context.json for the assistant
  → later: ingest actuals → compute error → update drift monitor → weekly retrain
```

**Replay mode (important for demos):** because we use a historical dataset, the system includes a "simulated clock". The operator picks an `origin_time` in the test period; the pipeline sees only data up to that time and later compares forecast vs. actuals. This makes the demo repeatable and prevents leakage.

---

## 9. System architecture

```
                ┌────────────┐   ┌──────────────┐   ┌─────────────┐
 Ausgrid data → │ Ingestion  │ → │ Feature      │ → │ Forecaster  │
 Weather API  → │ + QC       │   │ store (pq)   │   │ ensemble    │
 Calendar     → └────────────┘   └──────────────┘   └──────┬──────┘
                                                            │ P10/P50/P90
                        ┌──────────────┬────────────────────┼───────────────┐
                        ▼              ▼                    ▼               ▼
                   Alert engine   Optimizer (LP)     Drift monitor    Run bundle
                        │              │                    │          (files)
                        └──────┬───────┴──────────┬─────────┘               │
                               ▼                  ▼                         ▼
                        ControlAdapter       FastAPI  ◄────────────  LLM explainer
                        (sim / stub)            │                    (context only)
                                                ▼
                                          HTML dashboard
```

### 9.1 Repository layout
```
gridsight/
├── AGENTS.md
├── README.md
├── config.yaml
├── .env.example
├── Makefile
├── requirements.txt
├── docs/
│   ├── PRD.md
│   ├── DATA_SCHEMA.md
│   └── RESULTS.md
├── data/
│   ├── raw/            (git-ignored)
│   ├── processed/
│   └── cache/
├── src/gridsight/
│   ├── run.py          (CLI entry point: python -m gridsight.run)
│   ├── config.py
│   ├── data/           ingest.py, qc.py, aggregate.py, weather.py, calendar.py
│   ├── features/       builder.py
│   ├── models/         base.py, baselines.py, lgbm.py, ridge.py, ensemble.py, (mlp.py, cnn_bilstm.py)
│   ├── evaluation/     walkforward.py, metrics.py, report.py
│   ├── agent/          pipeline.py, scheduler.py, alerts.py, drift.py
│   ├── optimizer/      battery_lp.py, shift.py, tariff.py
│   ├── control/        adapter.py, simulated.py, bacnet_stub.py, guardrails.py
│   ├── llm/            client.py, prompts.py, explain.py
│   └── api/            main.py, schemas.py, routes/
├── web/                index.html, app.js, styles.css
├── runs/               (git-ignored)
├── models/             (git-ignored)
├── reports/
├── notebooks/          (optional Kaggle-ready training notebooks)
└── tests/
```

### 9.2 Tech stack
Python 3.11; pandas, numpy, pyarrow; LightGBM, scikit-learn; scipy (and optionally pulp); FastAPI + uvicorn; Pydantic v2; APScheduler; httpx; pytest; ruff; PyYAML; python-dotenv; `holidays`. Front end: plain HTML/JS with Chart.js or Plotly via CDN (with a vendored fallback copy if offline). v1.5: PyTorch.

### 9.3 Configuration (`config.yaml`) — key sections
`data` (paths, zone grouping + fallback rule, test period), `weather` (lat, lon, variables, cache dir, `backtest_noise` σ), `features` (lag list, rolling windows), `model` (LightGBM params, quantiles, ensemble method), `alerts` (thresholds, cooldown), `tariff` (bands, prices, demand charge), `battery` (capacity, powers, efficiency, SoC limits, `soc_initial_kwh`), `shiftable_loads`, `generator` (cost per kWh), `control` (`enabled: false`, `dry_run: true`, limits), `scheduler`, `llm` (provider/base URL/model read from env).

### 9.4 Environment variables (`.env.example`)
```
LLM_BASE_URL=        # OpenAI-compatible endpoint provided by the platform
LLM_API_KEY=         # the OpenCode-side API key
LLM_MODEL=           # model name to use
ALERT_WEBHOOK_URL=   # optional
GRIDSIGHT_ENV=dev
```

### 9.5 Makefile targets
| Target | Behaviour |
|--------|-----------|
| `make data` | Ingest + QC + aggregates → processed parquet + `reports/data_quality.json` |
| `make train` | Walk-forward backtest → `reports/backtest.md` |
| `make forecast [ORIGIN=...]` | One forecast cycle. **Default `ORIGIN` = the last data timestamp at or before the configured test-period end** (so replays are deterministic); explicit `ORIGIN` (local `Australia/Sydney`, or `...Z` for UTC) overrides it |
| `make serve` | Start FastAPI + dashboard on localhost |
| `make test` | Full pytest suite |
| `make demo` | **Defined target, not a phrase:** ensure `data/` built (skip if current), run `forecast` for the **canonical demo origin** (a hot day in the test period, pinned in `config.yaml` under `demo.origin` at M0), then `serve` and print the dashboard URL. Must go from no-op start to a forecasted dashboard in < 2 minutes (success metric §11) |

---

## 10. Output specifications

**`forecast.csv` (MVP deliverable)**
`timestamp_local, level, entity_id, horizon_slot, load_kw_p10, load_kw_p50, load_kw_p90, model_version, run_id, weather_source`

**`alerts.json`** — list of `{id, type, severity, level, entity_id, window_start, window_end, value, threshold, message}`

**`plan.json`** — `{mode:"advisory", tariff_version, battery:{schedule:[{slot,charge_kw,discharge_kw,soc_kwh}]}, grid_import_before, grid_import_after, cost_before, cost_after, saving, peak_before_kw, peak_after_kw, shifted_loads:[...], generator_recommendation:[...]}`

**`explain_context.json`** — compact, pre-aggregated facts (peak time/value, drivers such as temperature and day type, band width, last-7-day accuracy, alert list, plan summary, `run_id`, `generated_at`). This is the only input the LLM sees.

---

## 11. Success metrics

| Category | Metric | Target |
|----------|--------|--------|
| Accuracy | Portfolio nMAE (walk-forward) | < 8% (confirm on data) |
| Accuracy | Skill vs. seasonal-naive | ≥ 0.15 |
| Calibration | P10–P90 coverage | 75–85% |
| Decision value | Simulated bill reduction with battery plan | Report actual figure; expect low-to-mid single digit to low double digit % depending on tariff |
| Decision value | Peak reduction | Report kW and % |
| Reliability | Cycle success rate in replay of 30 consecutive days | 100% |
| UX | Time from `make demo` to dashboard showing a forecast | < 2 minutes |
| Trust | LLM answers containing numbers not in context | 0 in a 20-question test set |

---

## 12. Human oversight and safety

- Forecasts and plans are advisory; the UI shows an "Advisory only" badge.
- Control is off by default; enabling requires editing config and passing guardrail validation.
- Operators can override with one call/button; override state is persisted and logged.
- Every cycle has an audit trail (inputs hash, model version, config version, outputs, who/what triggered it) in the run bundle's `run.log`.
- The LLM cannot change forecasts, plans or config.
- Documented limitations: model drift, unusual events (grid outages in neighbouring regions, extreme heatwaves), historical residential dataset from the early-2010s (exact range per `DATA_SCHEMA.md`), so results demonstrate the method rather than current Australian grid behaviour. Keep manual override at all times.

---

## 13. Risks and mitigations

| Risk | Impact | Mitigation |
|------|--------|-----------|
| Weather API unreachable in the build environment | No weather features | Parquet cache, synthetic fallback clearly flagged, tests run offline |
| House-level forecasts are noisy | Looks like poor accuracy | Report portfolio and zone as headline, house level honestly, use sMAPE and quantile bands |
| Data leakage creeping in | Inflated metrics | Leakage unit test, walk-forward only, origin-time feature builder |
| Time overrun building everything | Nothing demo-able | Strict milestone order; MVP first |
| LLM hallucinating numbers | Loss of trust | Context-only prompting, template fallback, test set of questions |
| Optimizer infeasible edge cases | Crashes | Greedy fallback, feasibility tests, bounds on all variables, never emit negative-saving plan |
| Tariff assumptions seen as real | Misleading savings | Label as assumptions in UI and report |
| Scope creep into deep models | Missed deadline | Deep models are v1.5, behind the same interface; 7-day peaks deferred to M8 |

---

## 14. Acceptance criteria (definition of done)

**MVP done when:**
1. `make data` builds processed parquet and `reports/data_quality.json`.
2. `make train` runs walk-forward validation and writes `reports/backtest.md` with baselines vs. models.
3. `make forecast` (with a default or explicit origin) writes `runs/<origin>_<run_id>/forecast.csv` with 48 slots for the portfolio (and zones).
4. Leakage and shape tests pass (`make test`).
5. LightGBM+Ridge ensemble beats seasonal-naive on the walk-forward average.

**v1 done when additionally:**
6. `make serve` starts FastAPI and the dashboard with all tabs working on a replayed day.
7. Alerts fire on a known peak day in replay (and respect the FR-406 cooldown).
8. Optimizer shows a positive saving under the configured tariff with SoC and power limits respected (tested), and never emits a plan with `saving < 0`.
9. `/chat` answers the five supported questions using only context; fallback works with the LLM key removed.
10. `docs/RESULTS.md` contains tables and charts ready to paste into a report/paper.

---

## 15. Milestones and OpenCode prompts

Estimated for one focused working day for M0–M5, with M6–M8 as extension.

**M0 — Scaffold and data audit (≈ 30 min)**
> Read `docs/PRD.md` and `AGENTS.md`. Create the repository layout from section 9.1, `requirements.txt`, `Makefile` (all targets from §9.5, including a working `make demo` skeleton), `config.yaml`, `.env.example`, `.gitignore`. Then inspect the files in `data/raw/` (or the processed data I point you to), and write the real schema, row counts, exact date range, number of houses, and zone/postcode grouping into `docs/DATA_SCHEMA.md`. Also pick a hot day in the test period and pin it as `demo.origin` in `config.yaml`. Do not write modelling code yet. Ask me if the dataset location is unclear.

*Check:* repo tree exists; `DATA_SCHEMA.md` matches the real files; `demo.origin` is a real date with a documented peak.

**M1 — Ingestion, QC, aggregation (≈ 60 min)**
> Implement FR-101, FR-102 and the data-quality rules in section 4.6, including the zone fallback rule (4.2) and UTC-internal / Australia-Sydney-display time handling. Produce tidy parquet at house, zone and portfolio level plus `reports/data_quality.json`. Use "house" naming only. Add pytest tests for aggregation correctness (sum of houses equals zone equals portfolio).

*Check:* `make data` passes; test for sums passes.

**M2 — Weather, calendar, features (≈ 60 min)**
> Implement FR-103, FR-104, FR-105. Open-Meteo client with parquet caching and the offline/synthetic fallback clearly flagged. Build the leakage-safe feature builder and a pytest that proves no feature uses data after the forecast origin.

*Check:* feature table builds; leakage test passes.

**M3 — Baselines, models, walk-forward, MVP output (≈ 90 min)**
> Implement FR-201 to FR-208 (FR-206a stays out of scope here) and section 7. Baselines, LightGBM horizon-as-feature (including P10/P90 quantile models), Ridge, ensemble weights projected to the probability simplex, expanding-window walk-forward backtest with both weather scenarios, metrics module, and `reports/backtest.md`. Add the `make forecast` command that writes the next-24h `forecast.csv` for an `origin_time` (default per §9.5). No random k-fold anywhere.

*Check:* ensemble beats seasonal-naive; `forecast.csv` has 48 slots and plausible shape. **This is the MVP — commit and tag `v0.1-mvp`.**

**M4 — Agent pipeline, alerts, drift, run bundles (≈ 60 min)**
> Implement FR-301 to FR-306 and FR-401 to FR-406: `run_cycle`, replay mode with simulated clock, alert engine with cooldown, drift monitor, run bundles keyed on origin with audit log (inputs hash, model + config versions, trigger), scheduler wrapper (APScheduler) and CLI (`python -m gridsight.run --origin 2013-02-15T00:00` → `src/gridsight/run.py`).

*Check:* 7 consecutive replay days run without failure; a known hot-day triggers a peak alert; re-running the same origin does not duplicate alerts or bundles.

**M5 — Optimizer and control sandbox (≈ 75 min)**
> Implement FR-501 to FR-506 and FR-601 to FR-605. LP battery dispatch with SoC dynamics, efficiency, initial SoC and the demand-charge peak variable, deferrable load shifting, generator-vs-grid check, simulated and stub control adapters, guardrails. Include tests: SoC always within bounds, energy balance holds, `saving ≥ 0` (do-nothing comparison), infeasible input falls back gracefully.

*Check:* tests pass; `plan.json` shows positive saving on a peak day.

**M6 — API and dashboard (≈ 90 min)**
> Implement section 5.8 (including FR-801 idempotency) and 5.9. FastAPI with Pydantic schemas, serving `web/` static files. Dashboard tabs: Overview, Granularity, Alerts, Optimizer, Accuracy, Assistant, Settings. Use Chart.js or Plotly, colour-blind-safe palette, "Advisory only" badge, loading/error states.

*Check:* `make serve` shows a forecast with band for a replayed day; all tabs render with real data.

**M7 — LLM explainer (≈ 45 min)**
> Implement FR-701 to FR-705. OpenAI-compatible client reading `LLM_BASE_URL`, `LLM_API_KEY`, `LLM_MODEL` from env; context-only prompts; template fallback; `/chat` endpoint; and a 20-question test script that checks every number in the answer exists in `explain_context.json`.

*Check:* chat works with key; still returns a templated summary without the key.

**M8 — Deep models, 7-day peaks, drift retrain, results doc (stretch)**
> Add Embedding-MLP (5-day window predicts day 6) and CNN-BiLSTM-attention behind the `Forecaster` interface, include them in the walk-forward comparison, implement FR-206a (7-day daily-peak forecast) and the weekly retrain job, and generate `docs/RESULTS.md` with tables and charts (metrics by model, by hour, by weekday; optimizer savings; coverage plot).

---

## 16. Out-of-scope / future work

- Real SCADA / smart-meter / BACnet / MQTT integration.
- Live wholesale market API and automated bidding.
- Wind-farm and utility-scale solar forecasting.
- Fine-tuned domain SLM running on a self-hosted FastAPI endpoint in place of the external LLM.
- Multi-tenant SaaS, authentication, role-based access.
- Hierarchical reconciliation (house → zone → portfolio coherence) and probabilistic reconciliation.
- Reinforcement-learning-based dispatch.

---

## 17. `AGENTS.md` (copy this into the repo root)

```markdown
# GridSight — rules for the coding agent

## Project
Short-term energy demand forecasting agent. Full spec: docs/PRD.md. Build milestone by milestone; do only the milestone I name.

## Hard rules
1. Use the word "house" everywhere. Never "community" in code, columns, docs or UI.
2. Validation is walk-forward (expanding window) only. Never shuffled k-fold. Never fit scalers/encoders on future data.
3. Every feature at time t may use only data available at forecast origin. Keep the leakage test green.
4. The LLM never computes or modifies numbers. It receives explain_context.json and explains it. Always keep a template fallback.
5. Control is disabled and dry-run by default. Anything that can actuate must pass guardrails and be logged.
6. No secrets in the repo. Read keys from environment variables (.env, git-ignored).
7. Pipeline must run offline from caches. Any synthetic fallback data must be flagged in output columns and the UI.
8. Tariff, battery and generator values are assumptions; label them as assumptions wherever shown.
9. Outputs are advisory. Show an "Advisory only" badge in the UI.
10. All file paths come from config.yaml, relative to the project root. No hardcoded local paths.
11. Times are UTC internally, Australia/Sydney for display and CLI input; every timestamp is tz-aware.

## Conventions
- Python 3.11, type hints, ruff, pytest. Keep modules small and documented.
- Config lives in config.yaml; no magic numbers in code.
- The optimizer never emits a plan with negative saving (compare against do-nothing).
- After each milestone: run `make test`, summarize what changed, list any assumptions, and stop.

## Commands
make data | make train | make forecast | make serve | make test | make demo
(make demo = build data if needed, forecast the pinned demo.origin day, serve, print dashboard URL — see PRD §9.5)
```

---

## 18. Open assumptions (confirm quickly, defaults will be used otherwise)

1. Dataset: Ausgrid solar homes data already available locally or via the processed files from the earlier project; exact date range pinned at M0 in `DATA_SCHEMA.md`.
2. Zone definition: postcode groups (configurable), with the §4.2 fallback rule if no mapping exists.
3. Forecast granularity: 30-minute slots, 24h ahead.
4. Tariff, battery size, `soc_initial_kwh` and generator cost are illustrative defaults in `config.yaml`.
5. Weather: Open-Meteo for Sydney (default lat/lon in config); synthetic fallback only if no network; backtest noise σ = 2.0 °C / 50 W/m² unless tuned.
6. LLM: any OpenAI-compatible model available through the OpenCode API key; the model name goes in `.env`.
7. Demo origin: a hot day in the test period, chosen at M0 and pinned in `config.yaml` (`demo.origin`), so `make demo` is reproducible.
