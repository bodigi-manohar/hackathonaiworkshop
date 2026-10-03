# GridSight — team rules for the coding agent

Short-term energy demand forecasting agent. Full specs:
`docs/01_Member1_AI-ML_Manohar.md` (ML), the other two member docs, and the shared
JSON contracts in `contracts/sample/`.

## Hard rules
1. **Contract first.** All outputs must match `contracts/sample/` exactly (field
   names, 48 points, timezone Australia/Sydney, unit kW).
2. Stay in your own member folder. Cross-folder changes only via a PR touching
   `contracts/` approved by all three members.
3. Use the word **house**, never "community", in code, columns, docs or UI.
4. Walk-forward (expanding window) validation only. Never shuffled k-fold.
5. The LLM only explains pre-computed results; it never computes forecasts.
6. No secrets in Git. Keys live in `.env` (git-ignored), see `.env.example`.
7. All times stored UTC internally, displayed `Australia/Sydney`. One slot = 30 min.

## Workflow
- Small, working steps: finish a step, run its check, commit, move on.
- Merge into `main` only at sync points S0–S4.
