# CONTINUITY LEDGER

## Goal
Fix KPI Dashboard so values actually update when documents change or recalculation is triggered.
Success criteria: KPI cards show fresh LLM-computed values after recalculate is called.

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

### Done
- [Frontend] Auto-trigger recalculate when `is_stale` detected (was only console.log)
- [Backend] Fixed silent data loss in recalculate: `if k in final_values` filter was stripping all `_explanation` and `_trend_reasoning` fields the LLM returned
- [Backend] Added all explanation/reasoning fields to `KPIData` model so they survive `model_dump()` and `KPIResponse(**data)` round-trips
- [Backend] Added `ConfigDict(extra='allow')` to `KPIResponse`
- [Backend] Updated LLM prompt to explicitly request explanation and reasoning fields

### Now
- Awaiting user to restart backend and test

### Next
- Verify KPI cards display updated values after restart
- Optionally: add loading spinner to KPI cards while recalculation is in progress

## Open Questions
- UNCONFIRMED: Does the LLM reliably output all 40 JSON fields in one call? May need to truncate if token limit is hit.

## Working Set
- `/Users/hqnghi/git/simba/simba/api/dashboard_routes.py`
- `/Users/hqnghi/git/simba/frontend/src/pages/Dashboard.tsx`
- `/Users/hqnghi/git/simba/dashboard_kpis.json`
