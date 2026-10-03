# GridSight — Frontend (Member 3)

Dashboard for the GridSight short-term energy demand forecasting agent.
Plain HTML + CSS + JS with Chart.js (CDN). No build step.

## Run it

```powershell
# from gridsight/ — serves frontend/ and contracts/sample/
node scripts/serve.mjs 8080
# open http://localhost:8080/frontend/
```

Or open `frontend/index.html` directly in a browser (mock data is embedded, so it works offline too).

## Modes

| Mode | How | Data source |
|------|-----|-------------|
| **Mock (default)** | open page, or `?mock=1` | `contracts/sample/*.json` when served over HTTP; embedded copy in `mock-data.js` when opened via `file://` |
| **Live** | `?mock=0` or toggle in Settings tab | FastAPI at `http://localhost:8000` (Member 2). One config value: `API_BASE` in `api.js` |

The tab count, run selector, level/entity selectors and last tab are remembered in `localStorage`.

## Tabs

Overview · Granularity · Alerts · Optimizer · Accuracy · Assistant · Settings

Every view has loading, empty and error states (the error state has a Retry button).
The "Advisory only" badge and "assumption" labels are always visible where relevant.

## Files

| File | Purpose |
|------|---------|
| `index.html` | Shell: header, run/level/entity selectors, 7 tabs, panels |
| `styles.css` | Design tokens (light + dark), components |
| `app.js` | State, tab switching, data loading, states, footer |
| `api.js` | The ONLY file that calls `fetch`; MOCK flag |
| `mock-data.js` | Deterministic mock data + template chat answers |
| `charts.js` | Chart.js helpers + plugins (NOW line, threshold, peak marker, tariff bands) |
| `tabs/*.js` | One file per tab |

## Design system

**"Aurora Grid"** — an electric, colour-drenched control-room identity
(Linear/Framer-grade electric glass, built with the `high-end-visual-design` skill):
deep electric-indigo stage with a living aurora (drifting cyan/violet/coral glow
fields + faint power-grid lines), glass panels with gradient hairline tops,
cyan→violet energy accents on the brand mark, active tab and primary buttons,
and neon-glow chart lines. Clash Display for numerals/headings, Satoshi for UI,
JetBrains Mono for data. Actuals are solid electric cyan and the forecast is
dashed amber — a colour-blind-safe pair that also differs by dash style.
Footer carries a live Australia/Sydney clock.

## Smoke test

```powershell
# server must be running (see above)
node tests/smoke.mjs          # 19 checks: every tab, states, chat, refresh, screenshots
```

Screenshots land in `docs/screenshots/` (one per tab).

---

> Owner: Member 3 (Frontend & Visualization). Work on branch `m3-frontend`.
> Do not edit `ml/` or `backend/`; ask in the group chat (or a `contracts/` PR) if a field must change.
