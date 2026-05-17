"""
Coach dashboard aggregation built from MMA goals, OA session state, and a local
ledger stored in sys_cache.
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy.orm import Session

from app.db.sys_entities import SysCacheEntity
from app.services.mas.mas_gateway_service import MASGatewayService
from app.services.mas.patient_mapping_service import PatientMappingService

LEDGER_KEY_PREFIX = "mas_coach_ledger_"
WEEKDAY_LABELS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]


def _week_id() -> str:
    year, week, _ = datetime.now().isocalendar()
    return f"{year}-W{week:02d}"


def _today_str() -> str:
    return datetime.now().strftime("%Y-%m-%d")


def _normalize_window(window: Optional[str]) -> str:
    raw = str(window or "5").lower()
    return raw if raw in {"5", "10", "all"} else "5"


def _week_start() -> datetime:
    now = datetime.now()
    return now - timedelta(days=now.weekday())


def _week_range_label() -> str:
    start = _week_start()
    end = start + timedelta(days=6)
    return f"{start.strftime('%b')} {start.day} - {end.strftime('%b')} {end.day}"


def _coerce_goal_indices(values: Any, upper_bound: Optional[int] = None) -> List[int]:
    items: List[int] = []
    for value in values or []:
        if isinstance(value, int):
            parsed = value
        elif isinstance(value, str) and value.isdigit():
            parsed = int(value)
        else:
            continue
        if upper_bound is not None and not (0 <= parsed < upper_bound):
            continue
        if parsed not in items:
            items.append(parsed)
    return items


def _sanitize_days(days: Any) -> Dict[str, int]:
    if not isinstance(days, dict):
        return {}
    sanitized: Dict[str, int] = {}
    for key, value in days.items():
        if not isinstance(key, str):
            continue
        try:
            count = int(value)
        except (TypeError, ValueError):
            continue
        if count > 0:
            sanitized[key] = count
    return sanitized


def _sanitize_history(hist: Any) -> List[Dict[str, Any]]:
    items: List[Dict[str, Any]] = []
    for entry in hist or []:
        if not isinstance(entry, dict):
            continue
        week_id = entry.get("week_id")
        if not isinstance(week_id, str) or not week_id:
            continue
        try:
            planned = max(int(entry.get("planned", 0)), 0)
            completed = max(int(entry.get("completed", 0)), 0)
        except (TypeError, ValueError):
            continue
        rate_value = entry.get("rate")
        try:
            rate = None if rate_value is None else float(rate_value)
        except (TypeError, ValueError):
            rate = None
        items.append(
            {
                "week_id": week_id,
                "planned": planned,
                "completed": completed,
                "rate": rate,
            }
        )
    return items


def _summarize_week(ledger: Dict[str, Any], total: int) -> Dict[str, Any]:
    completed = len(_coerce_goal_indices(ledger.get("d", []), total))
    rate = round(100.0 * completed / total, 1) if total else None
    return {
        "week_id": ledger.get("wk") or _week_id(),
        "planned": total,
        "completed": completed,
        "rate": rate,
    }


def _append_history_snapshot(ledger: Dict[str, Any], snapshot: Dict[str, Any]) -> None:
    week_id = snapshot.get("week_id")
    if not week_id:
        return
    hist = [
        item
        for item in _sanitize_history(ledger.get("hist", []))
        if item.get("week_id") != week_id
    ]
    hist.append(snapshot)
    ledger["hist"] = hist[-26:]


def _weekday_distribution(ledger: Dict[str, Any], total: int) -> List[Dict[str, Any]]:
    days = _sanitize_days(ledger.get("days"))
    if not days:
        today_done = len(_coerce_goal_indices(ledger.get("td", []), total))
        if today_done:
            days[_today_str()] = today_done

    start = _week_start()
    distribution: List[Dict[str, Any]] = []
    for offset, label in enumerate(WEEKDAY_LABELS):
        day_key = (start + timedelta(days=offset)).strftime("%Y-%m-%d")
        distribution.append({"label": label, "count": int(days.get(day_key, 0))})
    return distribution


def _build_weekly_review(ledger: Dict[str, Any], total: int) -> Dict[str, Any]:
    current = _summarize_week(ledger, total)
    hist = _sanitize_history(ledger.get("hist"))
    previous_rate = hist[-1].get("rate") if hist else None
    current_rate = current.get("rate")
    vs_last_week = None
    if previous_rate is not None and current_rate is not None:
        vs_last_week = round(current_rate - float(previous_rate), 1)

    return {
        "week_range": _week_range_label(),
        "planned_count": current["planned"],
        "completed_count": current["completed"],
        "completion_rate": current_rate,
        "vs_last_week_rate": vs_last_week,
        "weekday_distribution": _weekday_distribution(ledger, total),
    }


def _build_overall_review(ledger: Dict[str, Any], total: int, window: str) -> Dict[str, Any]:
    current = _summarize_week(ledger, total)
    points = _sanitize_history(ledger.get("hist")) + [current]
    if window != "all":
        points = points[-int(window):]

    planned_total = sum(int(item.get("planned", 0)) for item in points)
    completed_total = sum(int(item.get("completed", 0)) for item in points)
    completion_rate = (
        round(100.0 * completed_total / planned_total, 1)
        if planned_total
        else None
    )

    completion_rate_trend: List[Dict[str, Any]] = []
    plan_vs_done_trend: List[Dict[str, Any]] = []
    cumulative_progress_trend: List[Dict[str, Any]] = []
    running_completed = 0
    for point in points:
        label = point.get("week_id")
        planned = int(point.get("planned", 0))
        completed = int(point.get("completed", 0))
        running_completed += completed
        completion_rate_trend.append({"label": label, "rate": point.get("rate")})
        plan_vs_done_trend.append(
            {"label": label, "planned": planned, "completed": completed}
        )
        cumulative_progress_trend.append(
            {"label": label, "completed_total": running_completed}
        )

    return {
        "window": window,
        "kpi": {
            "planned_total": planned_total,
            "completed_total": completed_total,
            "completion_rate": completion_rate,
        },
        "completion_rate_trend": completion_rate_trend,
        "plan_vs_done_trend": plan_vs_done_trend,
        "cumulative_progress_trend": cumulative_progress_trend,
    }


def _load_ledger(db: Session, account_id: str) -> Dict[str, Any]:
    key = LEDGER_KEY_PREFIX + account_id
    row = db.query(SysCacheEntity).filter_by(key=key).first()
    wk = _week_id()
    today = _today_str()
    default = {
        "wk": wk,
        "d": [],
        "day": today,
        "td": [],
        "days": {},
        "hist": [],
        "planned": 0,
        "_dirty": False,
    }
    if not row:
        return default

    try:
        data = json.loads(row.value)
    except json.JSONDecodeError:
        return default

    if data.get("wk") != wk:
        next_ledger = dict(default)
        next_ledger["hist"] = _sanitize_history(data.get("hist"))
        next_ledger["_dirty"] = True
        previous_total = max(int(data.get("planned") or 0), 0)
        _append_history_snapshot(next_ledger, _summarize_week(data, previous_total))
        return next_ledger

    if data.get("day") != today:
        data["day"] = today
        data["td"] = []
        data["_dirty"] = True

    data["d"] = _coerce_goal_indices(data.get("d", []))
    data["td"] = _coerce_goal_indices(data.get("td", []))
    data["days"] = _sanitize_days(data.get("days"))
    data["hist"] = _sanitize_history(data.get("hist"))
    try:
        data["planned"] = max(int(data.get("planned") or 0), 0)
    except (TypeError, ValueError):
        data["planned"] = 0
    data.setdefault("_dirty", False)
    return data


def _save_ledger(db: Session, account_id: str, ledger: Dict[str, Any]) -> None:
    key = LEDGER_KEY_PREFIX + account_id
    payload = dict(ledger)
    payload["wk"] = _week_id()
    payload["day"] = payload.get("day") or _today_str()
    payload["d"] = _coerce_goal_indices(payload.get("d", []))
    payload["td"] = _coerce_goal_indices(payload.get("td", []))
    payload["days"] = _sanitize_days(payload.get("days"))
    payload["hist"] = _sanitize_history(payload.get("hist"))[-26:]
    try:
        payload["planned"] = max(int(payload.get("planned") or 0), 0)
    except (TypeError, ValueError):
        payload["planned"] = 0
    payload.pop("_dirty", None)

    value = json.dumps(payload, separators=(",", ":"))
    row = db.query(SysCacheEntity).filter_by(key=key).first()
    now = datetime.now()
    if row:
        row.value = value
        row.update_time = now
    else:
        db.add(SysCacheEntity(key=key, value=value))
    db.commit()


def _infer_sma(text: str) -> Tuple[Dict[str, int], str]:
    lowered = (text or "").lower()
    specific = (
        1
        if len(text or "") > 15
        and re.search(r"\b(at least|every|times|walk|minutes|steps)\b", lowered)
        else 0
    )
    measurable = (
        1
        if re.search(r"\d+", text or "")
        or "step" in lowered
        or "minute" in lowered
        or "time" in lowered
        else 0
    )
    achievable = (
        1
        if re.search(r"\b(next week|every day|three times|daily|week)\b", lowered)
        or "week" in lowered
        else 0
    )
    score = specific + measurable + achievable
    if score >= 3:
        label = "SMART"
    elif score == 2:
        label = "Partially SMART"
    else:
        label = "Not SMART"
    return {"s": specific, "m": measurable, "a": achievable}, label


def _infer_activity(goal: str) -> str:
    lowered = goal.lower()
    if any(token in lowered for token in ("walk", "step", "jog")):
        return "walk"
    if any(token in lowered for token in ("run", "treadmill", "cardio")):
        return "run"
    if any(token in lowered for token in ("swim", "pool")):
        return "swim"
    if any(token in lowered for token in ("yoga", "stretch")):
        return "stretch"
    if any(token in lowered for token in ("tennis", "badminton", "sport")):
        return "sport"
    if "exercise" in lowered or "fitness" in lowered or "gym" in lowered:
        return "exercise"
    return "activity"


def _infer_duration_min(goal: str) -> Optional[int]:
    match = re.search(r"(\d+)\s*(?:min|minutes|mins)\b", goal, re.I)
    if match:
        return int(match.group(1))
    hour_match = re.search(r"(\d+)\s*(?:hour|hours|hr)\b", goal, re.I)
    if hour_match:
        return int(float(hour_match.group(1)) * 60)
    if "3000" in goal or "step" in goal.lower():
        return 30
    return None


def _next_workout_from_goals(
    goals: List[str], done_indices: List[int]
) -> Dict[str, Any]:
    if not goals:
        return {
            "summary": "",
            "activity_type": "",
            "duration_min": None,
            "intensity": "moderate",
            "scheduled_display": "",
            "source": "smart_goal",
            "confidence": "low",
        }

    next_index = None
    for index, _ in enumerate(goals):
        if index not in done_indices:
            next_index = index
            break
    if next_index is None:
        next_index = 0

    goal = goals[next_index]
    activity = _infer_activity(goal)
    intensity = "moderate"
    if activity in ("run", "sport"):
        intensity = "high"
    if activity in ("stretch", "walk"):
        intensity = "low"

    return {
        "summary": goal[:200],
        "goal_index": next_index,
        "activity_type": activity,
        "duration_min": _infer_duration_min(goal),
        "intensity": intensity,
        "scheduled_display": "This week (from your SMART goals)",
        "source": "smart_goal",
        "confidence": "medium",
    }


class CoachDashboardService:
    @staticmethod
    async def build_dashboard(
        db: Session, account_id: str, window: str = "5"
    ) -> Dict[str, Any]:
        window = _normalize_window(window)
        mapping = PatientMappingService(db)
        patient_id = mapping.get_or_create_patient_id(account_id)

        goals_data: Dict[str, Any] = {}
        try:
            goals_data = await MASGatewayService.call_mas_service(
                "mma", f"/patient_goals/{patient_id}", method="GET"
            )
        except Exception:
            goals_data = {}

        smart_goals = goals_data.get("smart_goals") or []
        if not isinstance(smart_goals, list):
            smart_goals = []

        total = len(smart_goals)
        ledger = _load_ledger(db, account_id)
        if ledger.get("planned") != total or ledger.get("_dirty"):
            ledger["planned"] = total
            _save_ledger(db, account_id, ledger)

        done_indices = _coerce_goal_indices(ledger.get("d", []), total)

        goals_detail: List[Dict[str, Any]] = []
        for index, text in enumerate(smart_goals):
            if not isinstance(text, str):
                continue
            sma, label = _infer_sma(text)
            goals_detail.append(
                {
                    "index": index,
                    "text": text,
                    "sma": sma,
                    "smart_label": label,
                    "completed": index in done_indices,
                }
            )

        completed_week = len(done_indices)
        weekly_rate = round(100.0 * completed_week / total, 1) if total else 0.0
        today_done = len(_coerce_goal_indices(ledger.get("td", []), total))
        today_pending = max(0, total - today_done)

        next_workout = _next_workout_from_goals(smart_goals, done_indices)
        weekly_review = _build_weekly_review(ledger, total)
        overall_review = _build_overall_review(ledger, total, window)

        next_review_payload: Dict[str, Any] = {}
        try:
            next_review_payload = await MASGatewayService.call_mas_service(
                "oa", f"/next_review_time/{patient_id}", method="GET"
            )
        except Exception:
            next_review_payload = {"next_review_time": None, "triggered": False}

        session_payload: Dict[str, Any] = {}
        try:
            session_payload = await MASGatewayService.call_mas_service(
                "oa", f"/session_status/{patient_id}", method="GET"
            )
        except Exception:
            session_payload = {}

        return {
            "patient_id": patient_id,
            "preferred_name": goals_data.get("preferred_name") or "",
            "smart_goals": smart_goals,
            "goals_detail": goals_detail,
            "next_workout": next_workout,
            "today_plan": {
                "completed": today_done,
                "pending": today_pending,
                "total": total,
            },
            "weekly_progress": {
                "completed": completed_week,
                "total": total,
                "rate": weekly_rate,
                "week_id": _week_id(),
            },
            "next_review_time": next_review_payload.get("next_review_time"),
            "next_review_triggered": next_review_payload.get("triggered", False),
            "session_status": session_payload,
            "weekly_review": weekly_review,
            "overall_review": overall_review,
        }

    @staticmethod
    async def apply_state_event(
        db: Session,
        account_id: str,
        event_type: str,
        goal_index: Optional[int] = None,
        note: Optional[str] = None,
    ) -> Dict[str, Any]:
        ledger = _load_ledger(db, account_id)
        mapping = PatientMappingService(db)
        patient_id = mapping.get_or_create_patient_id(account_id)

        goals_data: Dict[str, Any] = {}
        try:
            goals_data = await MASGatewayService.call_mas_service(
                "mma", f"/patient_goals/{patient_id}", method="GET"
            )
        except Exception:
            goals_data = {}

        smart_goals = goals_data.get("smart_goals") or []
        total = len(smart_goals) if isinstance(smart_goals, list) else 0

        if event_type not in {"goal_completed", "goal_skipped", "progress_refreshed"}:
            return {
                "ok": False,
                "changed": False,
                "event_type": event_type,
                "reason": "unsupported_event_type",
                "note": note,
            }

        changed = False
        if event_type == "goal_completed":
            if goal_index is None or not 0 <= goal_index < total:
                return {
                    "ok": False,
                    "changed": False,
                    "event_type": event_type,
                    "reason": "invalid_goal_index",
                    "note": note,
                }
            done_indices = _coerce_goal_indices(ledger.get("d", []))
            if goal_index not in done_indices:
                done_indices.append(goal_index)
                ledger["d"] = done_indices
                changed = True

                today_indices = _coerce_goal_indices(ledger.get("td", []))
                if goal_index not in today_indices:
                    today_indices.append(goal_index)
                    ledger["td"] = today_indices
                    days = _sanitize_days(ledger.get("days"))
                    today = _today_str()
                    days[today] = int(days.get(today, 0)) + 1
                    ledger["days"] = days
            else:
                return {
                    "ok": False,
                    "changed": False,
                    "event_type": event_type,
                    "reason": "goal_already_completed",
                    "note": note,
                }
        else:
            changed = True

        ledger["planned"] = total
        _save_ledger(db, account_id, ledger)
        return {
            "ok": True,
            "changed": changed,
            "event_type": event_type,
            "note": note,
        }
