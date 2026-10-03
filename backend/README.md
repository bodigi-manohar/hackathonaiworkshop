# backend/ — Member 2 (Backend & Integration)

FastAPI service that serves the ML run bundles (`runs/<run_id>/`) exactly as defined in
`contracts/sample/`. Everything the API returns must keep the contract field names and shapes.

Suggested surface (PRD §5.8 / Member-2 plan):

| Method | Path | Purpose |
|---|---|---|
| GET | `/health` | liveness + version |
| GET | `/entities` | portfolio / zone / house ids |
| GET | `/runs` | list run bundles (newest first) |
| GET | `/forecast?level=&entity_id=` | forecast + P10/P50/P90 |
| GET | `/forecast/csv` | 48-slot CSV download |
| GET | `/alerts` | alerts |
| GET | `/plan` | battery / load-shift plan |
| GET | `/metrics` | backtest + live accuracy |
| POST | `/run` | trigger `python -m ml.run_cycle --origin ...` |
| POST | `/chat` | grounded answer from `explain_context.json` |
| POST | `/control/override` | disable automation immediately |

Owner: Member 2. Work on branch `m2-backend`, keep `contracts/` changes approved by all three.
`data/`, `runs/`, `models/` are git-ignored — generate them locally or copy a bundle from Member 1.