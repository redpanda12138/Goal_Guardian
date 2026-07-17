import asyncio
import importlib
import json
import sys
from types import SimpleNamespace
from pathlib import Path

import pytest
from pydantic import ValidationError


SERVER_ROOT = Path(__file__).resolve().parents[1]


def import_server_module(monkeypatch, module_name):
    server_app_root = (SERVER_ROOT / "app").resolve()
    loaded_app = sys.modules.get("app")
    loaded_file = Path(getattr(loaded_app, "__file__", "")).resolve()
    if loaded_app is not None and server_app_root not in loaded_file.parents:
        for name in list(sys.modules):
            if name == "app" or name.startswith("app."):
                monkeypatch.delitem(sys.modules, name, raising=False)
    monkeypatch.syspath_prepend(str(SERVER_ROOT))
    return importlib.import_module(module_name)


@pytest.fixture
def workflow_contracts(monkeypatch):
    return SimpleNamespace(
        models=import_server_module(monkeypatch, "app.models.mas_workflow_models"),
        errors=import_server_module(monkeypatch, "app.services.mas.gateway_errors"),
        identity=import_server_module(monkeypatch, "app.services.mas.workflow_identity"),
        state=import_server_module(monkeypatch, "app.services.mas.workflow_state"),
    )


def test_workflow_message_request_requires_well_formed_stable_identifiers(workflow_contracts):
    request = workflow_contracts.models.WorkflowMessageRequest(
        mas_session_id="mas-session-123",
        request_id="request-123",
        workflow_version="v1",
        message="Review my weekly goal",
    )

    assert request.mas_session_id == "mas-session-123"
    assert request.request_id == "request-123"
    assert request.workflow_version == "v1"

    for invalid_field in ("mas_session_id", "request_id"):
        with pytest.raises(ValidationError):
            workflow_contracts.models.WorkflowMessageRequest(
                **{
                    "mas_session_id": "mas-session-123",
                    "request_id": "request-123",
                    "workflow_version": "v1",
                    "message": "Review my weekly goal",
                    invalid_field: "not a valid identifier!",
                }
            )

    with pytest.raises(ValidationError):
        workflow_contracts.models.WorkflowMessageRequest(
            mas_session_id="mas-session-123",
            request_id="request-123",
            workflow_version="version-one",
            message="Review my weekly goal",
        )


def test_thread_id_is_deterministic_for_account_session_and_version(workflow_contracts):
    first = workflow_contracts.identity.derive_thread_id("account-1", "mas-session-123", "v1")
    second = workflow_contracts.identity.derive_thread_id("account-1", "mas-session-123", "v1")

    assert first == second
    assert first != workflow_contracts.identity.derive_thread_id("account-2", "mas-session-123", "v1")
    assert first != workflow_contracts.identity.derive_thread_id("account-1", "mas-session-456", "v1")
    assert first != workflow_contracts.identity.derive_thread_id("account-1", "mas-session-123", "v2")


def test_session_ownership_rejects_cross_account_access(workflow_contracts):
    session = SimpleNamespace(id="mas-session-123", account_id="account-1")

    assert workflow_contracts.identity.validate_session_ownership(session, "account-1", "mas-session-123") is session

    with pytest.raises(workflow_contracts.identity.SessionOwnershipError):
        workflow_contracts.identity.validate_session_ownership(session, "account-2", "mas-session-123")

    with pytest.raises(workflow_contracts.identity.SessionOwnershipError):
        workflow_contracts.identity.validate_session_ownership(None, "account-1", "mas-session-123")


def test_legacy_bootstrap_contains_only_legacy_compat_and_json_safe_state(workflow_contracts):
    legacy_compat = workflow_contracts.state.LegacyCompatStateAdapter.bootstrap(
        legacy_turn_index=6,
        legacy_session_status="active",
    )
    state = workflow_contracts.state.bootstrap_workflow_state(
        account_id="account-1",
        mas_session_id="mas-session-123",
        request_id="request-123",
        workflow_version="v1",
        legacy_compat=legacy_compat,
    )

    assert legacy_compat == {
        "legacy_compat": {
            "legacy_turn_index": 6,
            "legacy_session_status": "active",
        }
    }
    assert state["thread_id"] == workflow_contracts.identity.derive_thread_id("account-1", "mas-session-123", "v1")
    assert "pending_action" not in state
    assert json.loads(json.dumps(state)) == state


def test_unknown_agent_decisions_and_tools_are_rejected(workflow_contracts):
    with pytest.raises(ValidationError):
        workflow_contracts.models.AgentDecision(kind="run_unbounded_action", message="no")

    with pytest.raises(ValidationError):
        workflow_contracts.models.ToolRequest(tool_name="delete_everything", arguments={})


def test_write_tool_request_requires_confirmation_without_execution(workflow_contracts):
    request = workflow_contracts.models.ToolRequest(
        tool_name=workflow_contracts.models.ToolName.MARK_GOAL_COMPLETE,
        arguments={"goal_index": 0},
        requires_confirmation=True,
    )
    decision = workflow_contracts.models.AgentDecision(
        kind=workflow_contracts.models.DecisionKind.AWAIT_CONFIRMATION,
        message="Would you like to mark this goal complete?",
        tool_request=request,
    )

    assert decision.tool_request.tool_name == workflow_contracts.models.ToolName.MARK_GOAL_COMPLETE
    assert decision.tool_request.requires_confirmation is True

    with pytest.raises(ValidationError):
        workflow_contracts.models.ToolRequest(
            tool_name=workflow_contracts.models.ToolName.MARK_GOAL_COMPLETE,
            arguments={"goal_index": 0},
            requires_confirmation=False,
        )


def test_decision_and_results_round_trip_through_json(workflow_contracts):
    decision = workflow_contracts.models.AgentDecision(
        kind=workflow_contracts.models.DecisionKind.REQUEST_TOOL,
        tool_request=workflow_contracts.models.ToolRequest(
            tool_name=workflow_contracts.models.ToolName.GET_WEEKLY_PROGRESS,
            arguments={"week": "2026-W29"},
        ),
    )
    tool_result = workflow_contracts.models.ToolResult(
        tool_name=workflow_contracts.models.ToolName.GET_WEEKLY_PROGRESS,
        status=workflow_contracts.models.ToolResultStatus.SUCCEEDED,
        payload={"completed": 2},
    )
    retrieval_result = workflow_contracts.models.RetrievalResult(
        retrieval_id="retrieval-123",
        source_id="guideline-123",
        content="Use a bounded weekly summary.",
        score=0.91,
        metadata={"tenant": "account-1"},
    )

    assert workflow_contracts.models.AgentDecision.parse_raw(decision.json()) == decision
    assert workflow_contracts.models.ToolResult.parse_raw(tool_result.json()) == tool_result
    assert workflow_contracts.models.RetrievalResult.parse_raw(retrieval_result.json()) == retrieval_result


@pytest.mark.parametrize(
    ("error_type", "category"),
    [
        ("UnknownMASServiceError", "unknown_service"),
        ("MASGatewayTimeoutError", "timeout"),
        ("MASGatewayHTTPError", "http"),
        ("MASGatewayTransportError", "transport"),
    ],
)
def test_gateway_errors_have_typed_categories(error_type, category, workflow_contracts):
    error = getattr(workflow_contracts.errors, error_type)("mma", "/decision", "connection failed")

    assert error.category == category
    assert error.service_name == "mma"
    assert error.endpoint == "/decision"


def test_gateway_raises_a_typed_error_for_an_unknown_service(monkeypatch, workflow_contracts):
    monkeypatch.setenv("DATABASE_URL", "sqlite:///:memory:")
    monkeypatch.setenv("SQL_ECHO", "false")
    monkeypatch.setenv("TOKEN_SECRET", "test-secret")
    monkeypatch.setenv("TOKEN_EXPIRE_TIME", "3600")

    MASGatewayService = import_server_module(
        monkeypatch, "app.services.mas.mas_gateway_service"
    ).MASGatewayService

    with pytest.raises(workflow_contracts.errors.UnknownMASServiceError):
        asyncio.run(MASGatewayService.call_mas_service("unknown", "/decision"))
