import asyncio
import importlib.util
import sys
import types
from datetime import datetime as real_datetime
from pathlib import Path

import pytest


class FakeSysCacheEntity:
    def __init__(self, key=None, value=None):
        self.key = key
        self.value = value
        self.update_time = None


class FakeQuery:
    def __init__(self, rows):
        self._rows = rows
        self._filters = {}

    def filter_by(self, **kwargs):
        self._filters = kwargs
        return self

    def first(self):
        for row in self._rows:
            if all(getattr(row, key, None) == value for key, value in self._filters.items()):
                return row
        return None


class FakeDBSession:
    def __init__(self):
        self.rows = []
        self.commits = 0

    def query(self, model):
        return FakeQuery(self.rows)

    def add(self, row):
        self.rows.append(row)

    def commit(self):
        self.commits += 1


class StubPatientMappingService:
    def __init__(self, db):
        self.db = db

    def get_or_create_patient_id(self, account_id):
        return f"patient-{account_id}"


class StubMASGatewayService:
    responses = {}

    @staticmethod
    async def call_mas_service(
        service_name, endpoint, method="POST", data=None, params=None, timeout=None
    ):
        key = (service_name, endpoint, method.upper())
        return StubMASGatewayService.responses.get(key, {})


class FixedDateTime(real_datetime):
    @classmethod
    def now(cls):
        return cls(2026, 4, 23, 9, 30, 0)


def load_coach_dashboard_module():
    module_name = "coach_dashboard_service_under_test"
    module_path = (
        Path(__file__).resolve().parents[1]
        / "app"
        / "services"
        / "mas"
        / "coach_dashboard_service.py"
    )

    app_pkg = types.ModuleType("app")
    app_pkg.__path__ = []
    db_pkg = types.ModuleType("app.db")
    db_pkg.__path__ = []
    services_pkg = types.ModuleType("app.services")
    services_pkg.__path__ = []
    mas_pkg = types.ModuleType("app.services.mas")
    mas_pkg.__path__ = []

    sys.modules["app"] = app_pkg
    sys.modules["app.db"] = db_pkg
    sys.modules["app.services"] = services_pkg
    sys.modules["app.services.mas"] = mas_pkg

    sys_entities_module = types.ModuleType("app.db.sys_entities")
    sys_entities_module.SysCacheEntity = FakeSysCacheEntity
    sys.modules["app.db.sys_entities"] = sys_entities_module

    gateway_module = types.ModuleType("app.services.mas.mas_gateway_service")
    gateway_module.MASGatewayService = StubMASGatewayService
    sys.modules["app.services.mas.mas_gateway_service"] = gateway_module

    patient_module = types.ModuleType("app.services.mas.patient_mapping_service")
    patient_module.PatientMappingService = StubPatientMappingService
    sys.modules["app.services.mas.patient_mapping_service"] = patient_module

    spec = importlib.util.spec_from_file_location(module_name, module_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    module.datetime = FixedDateTime
    return module


@pytest.fixture
def coach_module():
    StubMASGatewayService.responses = {
        ("mma", "/patient_goals/patient-acct-1", "GET"): {
            "preferred_name": "Alex",
            "smart_goals": [
                "Walk 30 minutes three times this week",
                "Stretch for 10 minutes every day",
            ],
        },
        ("oa", "/next_review_time/patient-acct-1", "GET"): {
            "next_review_time": "2026-04-24T09:00:00",
            "triggered": False,
        },
        ("oa", "/session_status/patient-acct-1", "GET"): {
            "latest_summary": "Kept up the routine this week.",
        },
    }
    return load_coach_dashboard_module()


@pytest.fixture
def db_session():
    return FakeDBSession()


def test_build_dashboard_includes_review_sections(coach_module, db_session):
    dashboard = asyncio.run(
        coach_module.CoachDashboardService.build_dashboard(
            db_session, "acct-1", window="5"
        )
    )
    assert "weekly_review" in dashboard
    assert "overall_review" in dashboard
    assert dashboard["overall_review"]["window"] == "5"


def test_save_ledger_preserves_weekly_history(coach_module, db_session):
    db_session.add(
        FakeSysCacheEntity(
            key=coach_module.LEDGER_KEY_PREFIX + "acct-1",
            value='{"wk":"2026-W16","day":"2026-04-16","d":[0,1],"td":[0],"hist":[]}',
        )
    )
    ledger = coach_module._load_ledger(db_session, "acct-1")
    assert ledger["hist"][-1]["week_id"] == "2026-W16"


def test_weekly_rollover_keeps_existing_history(coach_module, db_session):
    db_session.add(
        FakeSysCacheEntity(
            key=coach_module.LEDGER_KEY_PREFIX + "acct-1",
            value=(
                '{"wk":"2026-W16","day":"2026-04-16","d":[0],'
                '"td":[0],"planned":2,'
                '"hist":['
                '{"week_id":"2026-W14","planned":2,"completed":1,"rate":50.0},'
                '{"week_id":"2026-W15","planned":2,"completed":2,"rate":100.0}'
                ']}'
            ),
        )
    )

    ledger = coach_module._load_ledger(db_session, "acct-1")
    assert [item["week_id"] for item in ledger["hist"]] == [
        "2026-W14",
        "2026-W15",
        "2026-W16",
    ]


def test_build_dashboard_returns_weekly_review_distribution(
    coach_module, db_session
):
    dashboard = asyncio.run(
        coach_module.CoachDashboardService.build_dashboard(
            db_session, "acct-1", window="5"
        )
    )
    review = dashboard["weekly_review"]
    assert review["weekday_distribution"][0]["label"] == "Mon"
    assert len(review["weekday_distribution"]) == 7


def test_build_dashboard_returns_overall_review_trends(coach_module, db_session):
    dashboard = asyncio.run(
        coach_module.CoachDashboardService.build_dashboard(
            db_session, "acct-1", window="10"
        )
    )
    overall = dashboard["overall_review"]
    assert overall["window"] == "10"
    assert "completion_rate_trend" in overall
    assert "plan_vs_done_trend" in overall
    assert "cumulative_progress_trend" in overall


def test_goal_completed_updates_review_payloads(coach_module, db_session):
    asyncio.run(
        coach_module.CoachDashboardService.apply_state_event(
            db_session, "acct-1", "goal_completed", 0
        )
    )
    dashboard = asyncio.run(
        coach_module.CoachDashboardService.build_dashboard(
            db_session, "acct-1", window="5"
        )
    )
    assert dashboard["weekly_review"]["completed_count"] == 1
    assert dashboard["overall_review"]["kpi"]["completed_total"] >= 1


def test_invalid_goal_completed_event_is_rejected(coach_module, db_session):
    result = asyncio.run(
        coach_module.CoachDashboardService.apply_state_event(
            db_session, "acct-1", "goal_completed", 99
        )
    )
    assert result["ok"] is False
    assert result["reason"] == "invalid_goal_index"
    assert db_session.rows == []
