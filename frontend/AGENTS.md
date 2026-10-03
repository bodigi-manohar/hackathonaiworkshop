# Frontend rules (Member 3)

- Work only inside `frontend/`. Do not edit `backend/` or `ml/`.
- Plain HTML, CSS, JS with Chart.js from cdnjs. Files: `index.html`, `styles.css`,
  `app.js`, `api.js`, `charts.js`, `mock-data.js`, and `tabs/*.js` (one file per tab).
- Use skills `dashboard-contract-ui` and `ui-ux-pro-max` (or `frontend-design`) for every UI task.
- `api.js` is the only file that calls `fetch`. It supports MOCK mode using `contracts/sample`.
- Contract-first: every view is driven by the JSON contracts. Never hard-code numbers
  shown to the user (derive from the data).
- Every view has three states: loading, empty (no run yet), error (with retry button).
- Show units (kW, kWh) on axes and cards; show times in Australia/Sydney with the timezone label.
- Forecast chart: history solid line, P50 dashed line, P10–P90 as a shaded band
  (colour-blind-safe cyan/amber; series also differ by dash style).
- Always show the "Advisory only" badge. Tariff and battery values are labelled "assumption".
- Severity always uses colour AND an icon/text label.
- Chat tab shows "Answers use pre-computed results only." and tags `used_llm=false`
  as "template answer".
- Use the word **house**, never "community".
- After each step: open the page, click every tab, check the console, summarise changes, stop.
