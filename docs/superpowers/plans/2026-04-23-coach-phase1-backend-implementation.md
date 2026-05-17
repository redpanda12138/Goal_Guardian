# Coach Phase 1 Backend Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extend the MAS coach backend so `GET /mas/coach/dashboard` returns the new `weekly_review` and `overall_review` payloads, and `POST /mas/coach/goals/state-event` refreshes them consistently after goal completion.

**Architecture:** Keep the phase scoped to backend aggregation and state persistence. Reuse the existing `SysCacheEntity` ledger as the truth source for weekly completions, extend it to preserve per-week snapshots for trend windows, and expose a single optional `window` query parameter on the dashboard endpoint (`5 | 10 | all`, default `5`) so later frontend phases can request the exact review range without overfetching.

**Tech Stack:** FastAPI, SQLAlchemy, existing MAS gateway services, Python stdlib datetime/json helpers

---

## File Map

- Modify: `D:/SECOND WINDOW/NTU_Project/Dissertation/chatgpt-talkieai-main/talkieai-server/app/api/mas_routes.py`
- Modify: `D:/SECOND WINDOW/NTU_Project/Dissertation/chatgpt-talkieai-main/talkieai-server/app/services/mas/coach_dashboard_service.py`
- Modify: `D:/SECOND WINDOW/NTU_Project/Dissertation/chatgpt-talkieai-main/talkieai-server/app/models/mas_models.py`
- Create: `D:/SECOND WINDOW/NTU_Project/Dissertation/chatgpt-talkieai-main/talkieai-server/tests/test_coach_dashboard_service.py`

### Task 1: Lock the Dashboard API Contract

**Files:**
- Modify: `D:/SECOND WINDOW/NTU_Project/Dissertation/chatgpt-talkieai-main/talkieai-server/app/api/mas_routes.py`
- Modify: `D:/SECOND WINDOW/NTU_Project/Dissertation/chatgpt-talkieai-main/talkieai-server/app/models/mas_models.py`

- [ ] **Step 1: Add a failing backend test for the new dashboard shape**

Create `D:/SECOND WINDOW/NTU_Project/Dissertation/chatgpt-talkieai-main/talkieai-server/tests/test_coach_dashboard_service.py` with an assertion that the built dashboard contains `weekly_review`, `overall_review`, and `overall_review.window`.

```python
def test_build_dashboard_includes_review_sections():
    dashboard = asyncio.run(CoachDashboardService.build_dashboard(db_session, "acct-1", window="5"))
    assert "weekly_review" in dashboard
    assert "overall_review" in dashboard
    assert dashboard["overall_review"]["window"] == "5"
```

- [ ] **Step 2: Run the targeted test to confirm it fails**

Run: `python -m pytest talkieai-server/tests/test_coach_dashboard_service.py -k includes_review_sections -v`

Expected: FAIL because `build_dashboard` does not yet accept `window` and the new keys are absent.

- [ ] **Step 3: Extend the route and service signature**

Update `D:/SECOND WINDOW/NTU_Project/Dissertation/chatgpt-talkieai-main/talkieai-server/app/api/mas_routes.py` so the dashboard route accepts an optional query parameter:

```python
@router.get("/mas/coach/dashboard", name="Coach Dashboard")
async def get_coach_dashboard(
    window: str = "5",
    db: Session = Depends(get_db),
    account_id: str = Depends(get_current_account),
):
    data = await CoachDashboardService.build_dashboard(db, account_id, window=window)
```

Update `D:/SECOND WINDOW/NTU_Project/Dissertation/chatgpt-talkieai-main/talkieai-server/app/services/mas/coach_dashboard_service.py`:

```python
@staticmethod
async def build_dashboard(db: Session, account_id: str, window: str = "5") -> Dict[str, Any]:
    ...
```

- [ ] **Step 4: Validate the supported window values in one place**

Add a small normalizer in `D:/SECOND WINDOW/NTU_Project/Dissertation/chatgpt-talkieai-main/talkieai-server/app/services/mas/coach_dashboard_service.py`:

```python
def _normalize_window(window: Optional[str]) -> str:
    raw = str(window or "5").lower()
    return raw if raw in {"5", "10", "all"} else "5"
```

- [ ] **Step 5: Re-run the targeted test**

Run: `python -m pytest talkieai-server/tests/test_coach_dashboard_service.py -k includes_review_sections -v`

Expected: still FAIL, but now because the payload body has not been implemented yet.

- [ ] **Step 6: Commit the API contract work**

Run:

```bash
git add talkieai-server/app/api/mas_routes.py talkieai-server/app/services/mas/coach_dashboard_service.py talkieai-server/tests/test_coach_dashboard_service.py
git commit -m "feat: add coach dashboard review window contract"
```

### Task 2: Extend the Ledger to Preserve Weekly History

**Files:**
- Modify: `D:/SECOND WINDOW/NTU_Project/Dissertation/chatgpt-talkieai-main/talkieai-server/app/services/mas/coach_dashboard_service.py`
- Test: `D:/SECOND WINDOW/NTU_Project/Dissertation/chatgpt-talkieai-main/talkieai-server/tests/test_coach_dashboard_service.py`

- [ ] **Step 1: Add a failing test for weekly history snapshots**

Add a test that saves a ledger snapshot for multiple weeks and expects the service to retain week-level completion totals for trend generation.

```python
def test_save_ledger_preserves_weekly_history():
    _save_ledger(db_session, "acct-1", {"wk": "2026-W16", "d": [0, 1], "td": [0], "hist": []})
    ledger = _load_ledger(db_session, "acct-1")
    assert "hist" in ledger
```

- [ ] **Step 2: Run the targeted history test**

Run: `python -m pytest talkieai-server/tests/test_coach_dashboard_service.py -k weekly_history -v`

Expected: FAIL because the current ledger schema resets each week and does not preserve history.

- [ ] **Step 3: Add history-aware ledger helpers**

In `D:/SECOND WINDOW/NTU_Project/Dissertation/chatgpt-talkieai-main/talkieai-server/app/services/mas/coach_dashboard_service.py`, extend the ledger shape to include `hist` and preserve the prior week before rollover:

```python
default = {"wk": wk, "d": [], "day": today, "td": [], "hist": []}
```

Add helper functions with focused responsibilities:

```python
def _summarize_week(ledger: Dict[str, Any], total: int) -> Dict[str, Any]:
    completed = len([i for i in ledger.get("d", []) if isinstance(i, int) and 0 <= i < total])
    rate = round(100.0 * completed / total, 1) if total else None
    return {"week_id": ledger.get("wk"), "planned": total, "completed": completed, "rate": rate}

def _append_history_snapshot(ledger: Dict[str, Any], snapshot: Dict[str, Any]) -> None:
    hist = [x for x in ledger.get("hist", []) if isinstance(x, dict)]
    hist = [x for x in hist if x.get("week_id") != snapshot.get("week_id")]
    hist.append(snapshot)
    ledger["hist"] = hist[-26:]
```

- [ ] **Step 4: Update weekly rollover and save behavior**

When `_load_ledger` detects a week change, preserve the old week into `hist` before resetting the live counters. In `_save_ledger`, keep `hist` in the serialized payload and trim it before writing if necessary.

- [ ] **Step 5: Re-run the history test**

Run: `python -m pytest talkieai-server/tests/test_coach_dashboard_service.py -k weekly_history -v`

Expected: PASS.

- [ ] **Step 6: Commit the ledger history work**

Run:

```bash
git add talkieai-server/app/services/mas/coach_dashboard_service.py talkieai-server/tests/test_coach_dashboard_service.py
git commit -m "feat: persist coach weekly history snapshots"
```

### Task 3: Build `weekly_review` and `overall_review`

**Files:**
- Modify: `D:/SECOND WINDOW/NTU_Project/Dissertation/chatgpt-talkieai-main/talkieai-server/app/services/mas/coach_dashboard_service.py`
- Test: `D:/SECOND WINDOW/NTU_Project/Dissertation/chatgpt-talkieai-main/talkieai-server/tests/test_coach_dashboard_service.py`

- [ ] **Step 1: Add failing tests for weekly and overall review payloads**

Add assertions for:

```python
def test_build_dashboard_returns_weekly_review_distribution():
    dashboard = asyncio.run(CoachDashboardService.build_dashboard(db_session, "acct-1", window="5"))
    review = dashboard["weekly_review"]
    assert review["weekday_distribution"][0]["label"] == "Mon"
    assert len(review["weekday_distribution"]) == 7

def test_build_dashboard_returns_overall_review_trends():
    dashboard = asyncio.run(CoachDashboardService.build_dashboard(db_session, "acct-1", window="10"))
    overall = dashboard["overall_review"]
    assert overall["window"] == "10"
    assert "completion_rate_trend" in overall
    assert "plan_vs_done_trend" in overall
    assert "cumulative_progress_trend" in overall
```

- [ ] **Step 2: Run the review payload tests**

Run: `python -m pytest talkieai-server/tests/test_coach_dashboard_service.py -k "weekly_review or overall_review" -v`

Expected: FAIL because the review payload builders do not exist yet.

- [ ] **Step 3: Add focused payload builders**

Implement helper functions in `D:/SECOND WINDOW/NTU_Project/Dissertation/chatgpt-talkieai-main/talkieai-server/app/services/mas/coach_dashboard_service.py`:

```python
def _weekday_distribution(done_today: List[int]) -> List[Dict[str, Any]]:
    labels = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    today_idx = datetime.now().weekday()
    count = len([x for x in done_today if isinstance(x, int)])
    return [{"label": label, "count": count if idx == today_idx else 0} for idx, label in enumerate(labels)]

def _build_weekly_review(ledger: Dict[str, Any], total: int) -> Dict[str, Any]:
    completed = len([i for i in ledger.get("d", []) if isinstance(i, int) and 0 <= i < total])
    prev = None
    hist = [x for x in ledger.get("hist", []) if isinstance(x, dict)]
    if hist:
        prev = hist[-1].get("rate")
    current_rate = round(100.0 * completed / total, 1) if total else None
    delta = None if prev is None or current_rate is None else round(current_rate - float(prev), 1)
    return {
        "week_range": "",
        "planned_count": total,
        "completed_count": completed,
        "completion_rate": current_rate,
        "vs_last_week_rate": delta,
        "weekday_distribution": _weekday_distribution(ledger.get("td", [])),
    }
```

Implement an overall builder that slices `hist` by normalized window and emits the three graph series plus KPI totals.

- [ ] **Step 4: Wire the builders into `build_dashboard`**

Return these new keys from the main payload:

```python
"weekly_review": weekly_review,
"overall_review": overall_review,
```

- [ ] **Step 5: Re-run the review payload tests**

Run: `python -m pytest talkieai-server/tests/test_coach_dashboard_service.py -k "weekly_review or overall_review" -v`

Expected: PASS.

- [ ] **Step 6: Commit the review payload work**

Run:

```bash
git add talkieai-server/app/services/mas/coach_dashboard_service.py talkieai-server/tests/test_coach_dashboard_service.py
git commit -m "feat: add coach weekly and overall review payloads"
```

### Task 4: Keep State Events and Dashboard Refresh in Sync

**Files:**
- Modify: `D:/SECOND WINDOW/NTU_Project/Dissertation/chatgpt-talkieai-main/talkieai-server/app/api/mas_routes.py`
- Modify: `D:/SECOND WINDOW/NTU_Project/Dissertation/chatgpt-talkieai-main/talkieai-server/app/services/mas/coach_dashboard_service.py`
- Test: `D:/SECOND WINDOW/NTU_Project/Dissertation/chatgpt-talkieai-main/talkieai-server/tests/test_coach_dashboard_service.py`

- [ ] **Step 1: Add a failing test for state-event refresh**

Add a test asserting that after `apply_state_event(... goal_completed ...)`, the next dashboard rebuild returns updated `weekly_review.completed_count` and `overall_review.kpi.completed_total`.

```python
def test_goal_completed_updates_review_payloads():
    asyncio.run(CoachDashboardService.apply_state_event(db_session, "acct-1", "goal_completed", 0))
    dashboard = asyncio.run(CoachDashboardService.build_dashboard(db_session, "acct-1", window="5"))
    assert dashboard["weekly_review"]["completed_count"] == 1
    assert dashboard["overall_review"]["kpi"]["completed_total"] >= 1
```

- [ ] **Step 2: Run the state-event test**

Run: `python -m pytest talkieai-server/tests/test_coach_dashboard_service.py -k goal_completed_updates_review_payloads -v`

Expected: FAIL until the history snapshot and dashboard rebuild share the same updated counters.

- [ ] **Step 3: Make `apply_state_event` update review-ready ledger data**

In `D:/SECOND WINDOW/NTU_Project/Dissertation/chatgpt-talkieai-main/talkieai-server/app/services/mas/coach_dashboard_service.py`, keep the live week counters normalized after `goal_completed` and ensure `_save_ledger` is called with the same shape expected by the review builders.

- [ ] **Step 4: Make the route pass the selected window through after state events**

Update `D:/SECOND WINDOW/NTU_Project/Dissertation/chatgpt-talkieai-main/talkieai-server/app/api/mas_routes.py` so `post_coach_goal_state_event` rebuilds the dashboard with the same default window contract:

```python
dashboard = await CoachDashboardService.build_dashboard(db, account_id, window="5")
```

- [ ] **Step 5: Re-run the state-event test**

Run: `python -m pytest talkieai-server/tests/test_coach_dashboard_service.py -k goal_completed_updates_review_payloads -v`

Expected: PASS.

- [ ] **Step 6: Run the full Phase 1 backend test file**

Run: `python -m pytest talkieai-server/tests/test_coach_dashboard_service.py -v`

Expected: PASS for all new dashboard and state-event coverage in this file.

- [ ] **Step 7: Commit the state-event sync work**

Run:

```bash
git add talkieai-server/app/api/mas_routes.py talkieai-server/app/services/mas/coach_dashboard_service.py talkieai-server/tests/test_coach_dashboard_service.py
git commit -m "feat: sync coach state events with review payloads"
```

## Self-Review

- Spec coverage: This plan covers document Step 1 only: backend dashboard aggregation, `state-event`, and the new `weekly_review` / `overall_review` payload contract. It intentionally leaves Coach UI rendering, chart components, and Home/Chat refinements for later phases.
- Placeholder scan: Removed all `TBD` language and locked the window contract to `5 | 10 | all`.
- Type consistency: The plan consistently uses `window`, `weekly_review`, `overall_review`, `weekday_distribution`, `completion_rate_trend`, `plan_vs_done_trend`, and `cumulative_progress_trend`.
