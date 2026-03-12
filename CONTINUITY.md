# CONTINUITY LEDGER

## Goal
Debug and fix `start.sh` startup errors and ensure KPI Dashboard values update correctly.
Success criteria: `start.sh` runs all services successfully. KPI cards show fresh values after recalculate.

## Constraints/Assumptions
- Backend: FastAPI, Python, SQLite (LiteDB), LangChain LLM
- Frontend: React/TSX, Vite
- KPIs stored in `dashboard_kpis.json`

## Key Decisions
- KPIData model now includes all explanation/reasoning field declarations (30 extra fields)
- `KPIResponse` uses `model_config = ConfigDict(extra='allow')` to preserve any additional LLM fields
- Recalculate uses `final_values.update(result)` instead of filtered field merge
- Frontend auto-triggers recalculate when `is_stale=True` (instead of only logging)

## State

- [Backend] Fixed JSON structure mismatch in KPI recalculation: added aggressive flattening logic and robust string conversion for LLM outputs. This prevents Pydantic validation errors that were causing the server to fall back to stale cached data.
- [Backend] Verified end-to-end KPI recalculation via CLI/curl. `dashboard_kpis.json` now updates correctly with a fresh `last_updated` timestamp and the correct set of `source_doc_ids`.
- [Backend] Fixed FAISS initialization crash: now checks for `index.faiss` presence instead of just non-empty directory.
- [Frontend] Auto-trigger recalculate when `is_stale` detected.

### Now
- KPI recalculation is technically functional and robust.

### Next
- Improve the quality of KPI extraction by increasing the number of documents used in context or implementing a more targeted retrieval (e.g., searching for specific KPI keywords).
- Add a loading state to the frontend dashboard during recalculation.

## Open Questions
- UNCONFIRMED: Does the LLM reliably output all 40 JSON fields in one call? May need to truncate if token limit is hit.

## Working Set
- `/Users/hqnghi/git/simba/simba/api/dashboard_routes.py`
- `/Users/hqnghi/git/simba/frontend/src/pages/Dashboard.tsx`
- `/Users/hqnghi/git/simba/dashboard_kpis.json`
