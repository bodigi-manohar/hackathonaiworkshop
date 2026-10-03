# Team Plan 1 of 3 — Member 1: AI/ML Engineer

**Project:** GridSight — Short-Term Energy Demand Forecasting Agent (Problem 27)
**For:** Manohar
**Read in this order:** Section A (team overview, same in all 3 docs), then Section B (your own plan).

---

## A. Team overview (same in all 3 docs)

**Project:** GridSight — a short-term energy demand forecasting agent (Problem 27).
It reads smart-meter style data (Ausgrid dataset) + weather, forecasts the next 24 hours (48 half-hour slots) with an uncertainty band, raises peak alerts, suggests a battery / load-shifting plan, and explains results in plain language through a chat box. Everything is **advisory only**.

| Member | Person | Role | Owns folder | Main output |
|--------|--------|------|-------------|-------------|
| **1** | Manohar | AI/ML Engineer | `ml/` | Clean data, features, trained models, forecast files, accuracy report |
| **2** | Chaitu | Backend & Integration | `backend/` | REST API, database, alerts, optimizer, LLM chat, scheduler |
| **3** | (name) | Frontend & Visualization | `frontend/` | Dashboard: graphs, alerts, optimizer view, chat UI |

**Golden rules**
1. **Contract first.** All three of us build against the same JSON files in `contracts/`. Nobody waits for anybody: Member 3 uses sample files, Member 2 uses sample files, Member 1 produces the real ones.
2. **Stay in your folder.** Never edit another member's folder. Need a change? Ask in the group chat, or open a PR touching only `contracts/` that all three approve.
3. **Small, working steps.** Finish a step, run its check, commit, then move on.
4. Use the word **house** (never "community") in code, columns and UI.
5. The AI chat only **explains pre-computed results**. It never calculates a forecast.
6. No secrets in Git. Keys live in `.env` (git-ignored). See `.env.example`.

### Repo layout (create once, Member 2 or 1 pushes the empty skeleton)
```
gridsight/
├── contracts/          # shared JSON examples + schemas (all 3 approve changes)
│   └── sample/         # forecast.json, alerts.json, plan.json, metrics.json, explain_context.json, entities.json
├── data/               # raw + processed data (git-ignored, big)
├── runs/               # one folder per forecast run (git-ignored)
│   └── <run_id>/       # forecast.json, metrics.json, explain_context.json, alerts.json, plan.json
├── ml/                 # Member 1
├── backend/            # Member 2
├── frontend/           # Member 3
├── docs/               # these 3 docs + results
├── .env.example
└── README.md
```

### The shared contract (copy these into `contracts/sample/` on day 1)
All times are ISO-8601 with timezone `Australia/Sydney`. Units: kW. One slot = 30 minutes, 48 slots = 24 h.

**`forecast.json`**
```json
{
  "run_id": "2013-02-15T00-00",
  "origin_time": "2013-02-15T00:00:00+11:00",
  "level": "portfolio",
  "entity_id": "all",
  "unit": "kW",
  "slot_minutes": 30,
  "model_version": "ensemble-v1",
  "weather_source": "open-meteo",
  "points": [
    {"slot": 0, "timestamp": "2013-02-15T00:00:00+11:00", "p10": 118.4, "p50": 125.2, "p90": 133.9}
  ],
  "history": [
    {"timestamp": "2013-02-14T00:00:00+11:00", "actual": 121.7}
  ]
}
```
`level` is `portfolio`, `zone` or `house`. `points` always has 48 items. `history` is the previous 48 slots of actual load.

**`alerts.json`**
```json
[
  {"id": "a1", "type": "peak", "severity": "warn", "level": "portfolio", "entity_id": "all",
   "window_start": "2013-02-15T18:00:00+11:00", "window_end": "2013-02-15T20:00:00+11:00",
   "value": 182.5, "threshold": 170.0, "message": "Evening peak above threshold"}
]
```
`type`: `peak` | `ramp` | `low_confidence` | `model_drift` | `heatwave`. `severity`: `info` | `warn` | `critical`.

**`plan.json`**
```json
{
  "mode": "advisory",
  "assumptions": "Illustrative tariff and battery values",
  "slots": [
    {"slot": 0, "price": 0.18, "grid_before_kw": 125.2, "grid_after_kw": 140.0,
     "battery_charge_kw": 14.8, "battery_discharge_kw": 0.0, "soc_kwh": 60.0}
  ],
  "cost_before": 410.2, "cost_after": 372.9, "saving": 37.3,
  "peak_before_kw": 182.5, "peak_after_kw": 160.1,
  "generator_recommendation": [{"slot": 36, "message": "Generator cheaper than grid for this slot"}]
}
```

**`metrics.json`**
```json
{
  "scope": "walk_forward_backtest",
  "by_model": [
    {"model": "seasonal_naive", "mae": 12.4, "rmse": 16.0, "nmae": 0.098, "skill": 0.0},
    {"model": "ensemble", "mae": 9.8, "rmse": 13.1, "nmae": 0.077, "skill": 0.21}
  ],
  "by_hour": [{"hour": 0, "mae": 8.1}],
  "by_weekday": [{"weekday": 0, "mae": 9.5}],
  "coverage_p10_p90": 0.79,
  "last_7_days_mae": 10.2
}
```

**`explain_context.json`** (the ONLY thing the chat AI sees)
```json
{
  "run_id": "2013-02-15T00-00",
  "peak": {"time": "2013-02-15T18:30:00+11:00", "p50_kw": 182.5, "p90_kw": 195.0},
  "total_kwh_next_24h": 3120.0,
  "drivers": ["Hot afternoon (max 36 C)", "Weekday evening", "Low solar after 17:00"],
  "band_width_note": "P10-P90 band is widest at the evening peak",
  "accuracy_last_7_days": {"mae_kw": 10.2, "skill_vs_naive": 0.21},
  "alerts_summary": ["1 peak alert (warn)"],
  "plan_summary": {"saving": 37.3, "peak_reduction_kw": 22.4}
}
```

**`entities.json`**
```json
{"portfolio": ["all"], "zone": ["2000", "2010"], "house": ["1", "2", "3"]}
```

### The API (Member 2 builds, Member 3 consumes)
Base URL: `http://localhost:8000`. Every GET accepts optional `run_id` (default = latest run).

| Method | Path | Returns |
|--------|------|---------|
| GET | `/health` | `{"status":"ok","version":"..."}` |
| GET | `/entities` | `entities.json` |
| GET | `/runs` | list of `{run_id, origin_time, created_at}` newest first |
| GET | `/forecast?level=portfolio&entity_id=all` | `forecast.json` |
| GET | `/forecast/csv?level=portfolio&entity_id=all` | CSV download of the 48 slots |
| GET | `/alerts` | `alerts.json` |
| GET | `/plan` | `plan.json` |
| GET | `/metrics` | `metrics.json` |
| POST | `/run` body `{"origin_time": "2013-02-15T00:00:00+11:00"}` | `{"run_id": "..."}` (runs a full cycle) |
| POST | `/chat` body `{"question": "...", "run_id": null}` | `{"answer": "...", "used_llm": true}` |
| POST | `/control/override` | `{"control_enabled": false}` |

### Sync points (stop, merge, test together)
| Sync | When | What must be true |
|------|------|-------------------|
| **S0** | Start, 20 min | Repo created, `contracts/sample/*` committed, everyone has OpenCode + skills + AGENTS.md set up |
| **S1** | ~1.5 h | Member 1 pushes a **first real-format forecast** (even from a simple baseline) into `runs/`. Member 2's API serves it. Member 3's dashboard draws it |
| **S2** | ~4 h | Real LightGBM/ensemble forecast + metrics flowing. Alerts + plan available from API. Dashboard shows all tabs |
| **S3** | ~6 h | Chat works end to end. Replay a few days. Fix integration bugs |
| **S4** | Final | Demo run-through, screenshots, results doc |

(Times are a guide for one focused working day. Stretch items come after S3.)

### Git workflow (simple)
- Branches: `m1-ml`, `m2-backend`, `m3-frontend`. Merge into `main` only at sync points (or when a step is fully done and tested).
- Commit after every finished step with a clear message, e.g. `m2: add /forecast endpoint`.
- Before merging: `git pull --rebase origin main`, run your tests.

### How to add GitHub skills to OpenCode (all members)
OpenCode finds skills in `.opencode/skills/<name>/SKILL.md` (also `.claude/skills/` and `.agents/skills/`). Each skill is just a folder with a `SKILL.md`.
```
git clone --depth 1 https://github.com/anthropics/skills.git /tmp/anthropic-skills
mkdir -p .opencode/skills
cp -r /tmp/anthropic-skills/skills/<skill-name> .opencode/skills/
```
Windows: use Git Bash for the same commands, or copy the folder in File Explorer to `.opencode\skills\`. Then **restart OpenCode**. Type `/skills` (or ask "which skills do you have?") to check.

Safety and sanity tips:
- Install **only 2 to 4 skills**. Many skills means a crowded context and worse answers.
- A skill is instructions your agent will obey. **Read the `SKILL.md` of any community skill before installing it.** The official `anthropics/skills` repo is the safest source.
- Custom project skills (given in your doc) are tiny; copy them into `.opencode/skills/<name>/SKILL.md` exactly.

---

## B. Your part — Member 1: AI/ML Engineer (Manohar)

### B1. What you deliver
| # | Deliverable | Where | Who uses it |
|---|-------------|-------|-------------|
| 1 | Clean tidy data (house, zone, portfolio) | `data/processed/` | You |
| 2 | Weather + calendar + features | `ml/features/` | You |
| 3 | Baselines + LightGBM + Ridge ensemble with P10/P50/P90 | `ml/models/` | You |
| 4 | Walk-forward accuracy report | `runs/<id>/metrics.json`, `docs/RESULTS.md`, `reports/results.xlsx` | Member 2, 3, professor |
| 5 | **Run bundle**: `forecast.json`, `metrics.json`, `explain_context.json` | `runs/<run_id>/` | Member 2 reads, Member 3 shows |
| 6 | One command to run a cycle | `python -m ml.run_cycle --origin 2013-02-15T00:00` | Member 2's `/run` calls this |
| 7 | `entities.json` (list of zones and houses) | `contracts/sample/` and `data/processed/` | Member 2, 3 |

You do **not** build the API, database, alerts, optimizer, chat or UI. Stay on data and models.

### B2. Skills to integrate (best picks for you)
| Skill | Source | Why you need it |
|-------|--------|-----------------|
| `skill-creator` | GitHub `anthropics/skills` (official) | Lets OpenCode help you turn your rules into new skills and improve them |
| `xlsx` | GitHub `anthropics/skills` (official) | Builds the results spreadsheet (model comparison tables) you already present to your professor |
| `forecasting-guardrails` | **Custom, copy from below** | Keeps leakage, k-fold and metric mistakes out of the code. This is the one that matters most |

There is no official ML-forecasting skill, so the custom one is the real value. Optional later: `docx` or `pptx` from the same repo for the paper/report.

Install:
```
git clone --depth 1 https://github.com/anthropics/skills.git /tmp/anthropic-skills
mkdir -p .opencode/skills
cp -r /tmp/anthropic-skills/skills/skill-creator .opencode/skills/
cp -r /tmp/anthropic-skills/skills/xlsx .opencode/skills/
```
Then create `.opencode/skills/forecasting-guardrails/SKILL.md` with this content:
```
---
name: forecasting-guardrails
description: Use when writing or reviewing time-series forecasting code in this project (features, training, validation, metrics, output files) to prevent leakage and misleading results.
---

## Rules
1. Validation is walk-forward (expanding window) only. Never shuffle, never random KFold.
2. A feature at time t may only use data available at the forecast origin. Shift before rolling.
3. Fit scalers and encoders on the training window only.
4. Always report a seasonal-naive baseline (same slot yesterday) next to every model.
5. Compute solar metrics on daylight slots only (about 58 percent of rows are night zeros).
6. A 24 h forecast has exactly 48 slots with distinct slot numbers and a plausible daily shape. Test it.
7. Use the word house, never community.
8. Write outputs exactly as in contracts/sample. Validate the JSON before saying a task is done.
9. Quantiles must satisfy p10 <= p50 <= p90 for every slot.

## Before finishing any task
- Run pytest. Confirm the leakage test passes.
- State which baseline the new model beat and by how much.
- Mention any assumption you made.
```
Restart OpenCode after adding skills.

### B3. `AGENTS.md` for your folder (save as `ml/AGENTS.md`, or merge into root `AGENTS.md`)
```
# ML rules (Member 1)
- Work only inside ml/, data/, runs/, reports/. Do not edit backend/ or frontend/.
- Python 3.11, type hints, pytest. Config in ml/config.yaml, no magic numbers.
- Use skill forecasting-guardrails for every modelling task.
- Output files must match contracts/sample exactly (field names, 48 points, timezone Australia/Sydney).
- Never use shuffled k-fold. Walk-forward only.
- Weather: Open-Meteo with parquet cache; if offline use a flagged synthetic fallback (weather_source = "synthetic").
- After each step: run tests, summarise changes, stop.
```

### B4. Step-by-step plan
Time estimates are for one focused day. Do the steps **in order**.

**Step 1 — Setup (20 min)**
- Clone repo, switch to branch `m1-ml`, install the skills above, add `AGENTS.md`.
- Create `ml/`, `requirements.txt` (pandas, numpy, pyarrow, lightgbm, scikit-learn, scipy, requests, holidays, pyyaml, pytest, openpyxl).
- Commit the contract samples into `contracts/sample/` (take them from section A) with the whole team (this is sync point S0).
- *Check:* `pytest` runs (even with zero tests) and `/skills` lists your skills.

**Step 2 — Data audit and tidy tables (45 min)**
Prompt for OpenCode:
> Inspect the Ausgrid files in `data/raw/` (or the processed data I point you to). Write the real schema, date range, number of houses and postcode groups to `docs/DATA_SCHEMA.md`. Then build tidy parquet tables with columns `timestamp, house_id, zone_id, load_kw, solar_kw, net_load_kw` for house level, plus zone and portfolio aggregates. Handle missing slots and duplicates, store UTC internally, and write `data/processed/entities.json`. Add a test that sum of houses = zone = portfolio. Use "house" naming only.
- *Check:* aggregation test passes; row counts look right.

**Step 3 — Ship a first real-format forecast fast (30 min) — this unblocks Members 2 and 3**
Prompt:
> Implement a seasonal-naive baseline (same slot yesterday) and write `runs/<run_id>/forecast.json` for the portfolio level exactly like `contracts/sample/forecast.json`. Use p50 = naive value and p10/p90 = p50 minus/plus 10 percent for now. Include 48 points and the previous 48 slots as `history`. Add `python -m ml.run_cycle --origin <time>`.
- *Check:* JSON matches the contract; tell Members 2 and 3 to pull. **This is sync point S1.**

**Step 4 — Weather, calendar and features (60 min)**
Prompt:
> Use the forecasting-guardrails skill. Add an Open-Meteo client (temperature, humidity, apparent temperature, cloud cover, shortwave radiation, wind, precipitation) with parquet caching and a flagged synthetic fallback. Add NSW holidays and calendar features. Build a leakage-safe feature builder with lags (1, 2, 48, 96, 336 slots), rolling mean/std, calendar and weather features. Write a pytest proving no feature uses data after the forecast origin.
- *Check:* leakage test passes; feature table builds.

**Step 5 — Models and walk-forward backtest (90 min)**
Prompt:
> Use forecasting-guardrails. Implement baselines (seasonal naive, weekly naive), Ridge, LightGBM (direct multi-horizon, 48 slots), and P10/P90 LightGBM quantile models. Blend Ridge and LightGBM with non-negative weights learned on a validation fold. Run an expanding-window walk-forward backtest over at least 6 monthly folds with a daily 00:00 origin. Compute MAE, RMSE, nMAE, skill vs seasonal naive, peak error, P10-P90 coverage, by hour and by weekday. Save `runs/<id>/metrics.json` in the contract format and `reports/backtest.md`.
- *Check:* ensemble beats seasonal naive; coverage is roughly 75 to 85 percent; p10 <= p50 <= p90. **This is the MVP.**

**Step 6 — Real run bundle (30 min)**
Prompt:
> Update `ml.run_cycle` to use the trained ensemble: build features at the origin, forecast portfolio, every zone and every house, and write forecast files per entity, `metrics.json` and `explain_context.json` into `runs/<run_id>/`. Name files `forecast_<level>_<entity>.json` and keep `forecast.json` as the portfolio one. Replay mode: the run may only see data up to the origin time.
- *Check:* Member 2's `/forecast` returns your real output. **This is sync point S2.**

**Step 7 — explain_context facts (20 min)**
Prompt:
> Build `explain_context.json` from the run: peak time and value, total kWh, up to three plain-language drivers (for example hot day, weekday evening, low solar after 17:00) derived from weather and calendar features, accuracy of the last 7 days, and band width note. Only facts that exist in the data. No free-text guesses.
- *Check:* every number can be traced to a file. Member 2's chat uses only this file.

**Step 8 — Results for the professor (30 min)**
Prompt (uses the `xlsx` skill):
> Create `reports/results.xlsx` with sheets: model comparison (all folds and average), error by hour, error by weekday, and coverage. Also write `docs/RESULTS.md` with the same tables and the key findings, including honest house-level error and the night-zero solar caveat.

**Step 9 — Stretch (only after S3)**
- Add Embedding-MLP (5-day input predicts day 6) and CNN-BiLSTM with attention behind the same model interface and compare in the same backtest.
- Drift check: rolling 7-day MAE versus training MAE, written into `metrics.json` as `drift_ratio` for Member 2's alert engine.
- Optional: a TimesFM-style zero-shot model as an extra comparison row.

### B5. Definition of done (your checklist)
- [ ] `python -m ml.run_cycle --origin 2013-02-15T00:00` writes a valid run bundle in under a few minutes
- [ ] 48 slots, ordered, `p10 <= p50 <= p90`, timezone correct
- [ ] Leakage test and aggregation test pass
- [ ] Ensemble beats seasonal naive on the walk-forward average
- [ ] `metrics.json` and `explain_context.json` follow the contract
- [ ] `docs/DATA_SCHEMA.md`, `docs/RESULTS.md`, `reports/results.xlsx` exist
- [ ] 7 consecutive replay days run without failure

### B6. What you need from others, and what they need from you
| You need | From | By |
|----------|------|----|
| Repo skeleton and `contracts/` agreed | Everyone | S0 |
| Tell you if a field name or shape must change | Member 2 / 3 | anytime, via contract PR |
| **They need** a first forecast file | You to Members 2, 3 | S1 (Step 3) |
| **They need** real models and metrics | You to Members 2, 3 | S2 (Steps 5, 6) |
| **They need** `explain_context.json` | You to Member 2 | S2 (Step 7) |

### B7. Tips
- If OpenCode wants to "improve" the validation with random splits, say no and point to the guardrails skill.
- Headline accuracy at **portfolio and zone** level. Report house level honestly: it is noisy, that is expected.
- Keep each OpenCode prompt to one step. Commit after each.
