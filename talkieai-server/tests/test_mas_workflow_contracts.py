import asyncio
import importlib
import json
import sys
import types
from datetime import datetime
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

    with pytest.raises(workflow_contracts.errors.UnknownMASServiceError) as captured:
        asyncio.run(MASGatewayService.call_mas_service("unknown", "/decision"))
    assert isinstance(captured.value, ValueError)


def test_write_tool_requires_confirmation_when_the_field_is_omitted(workflow_contracts):
    with pytest.raises(ValidationError):
        workflow_contracts.models.ToolRequest(
            tool_name=workflow_contracts.models.ToolName.MARK_GOAL_COMPLETE,
            arguments={"goal_index": 0},
        )


def test_confirmed_write_tool_can_only_be_an_await_confirmation_decision(
    workflow_contracts,
):
    request = workflow_contracts.models.ToolRequest(
        tool_name=workflow_contracts.models.ToolName.MARK_GOAL_COMPLETE,
        arguments={"goal_index": 0},
        requires_confirmation=True,
    )

    with pytest.raises(ValidationError):
        workflow_contracts.models.AgentDecision(
            kind=workflow_contracts.models.DecisionKind.REQUEST_TOOL,
            tool_request=request,
        )


@pytest.mark.parametrize(
    "factory",
    [
        lambda models: models.ToolRequest(
            tool_name=models.ToolName.GET_WEEKLY_PROGRESS,
            arguments={"invalid": {"not-json"}},
        ),
        lambda models: models.ToolResult(
            tool_name=models.ToolName.GET_WEEKLY_PROGRESS,
            status=models.ToolResultStatus.SUCCEEDED,
            payload={"invalid": datetime(2026, 1, 1)},
        ),
        lambda models: models.RetrievalResult(
            retrieval_id="retrieval-123",
            source_id="guideline-123",
            content="content",
            score=float("nan"),
            metadata={"invalid": object()},
        ),
    ],
)
def test_contract_payloads_reject_non_json_values(factory, workflow_contracts):
    with pytest.raises(ValidationError):
        factory(workflow_contracts.models)


def test_contract_versions_are_fixed_to_the_supported_version(workflow_contracts):
    with pytest.raises(ValidationError):
        workflow_contracts.models.WorkflowMessageRequest(
            contract_version="v2",
            mas_session_id="mas-session-123",
            request_id="request-123",
            workflow_version="v1",
            message="Review my weekly goal",
        )

    with pytest.raises(ValidationError):
        workflow_contracts.models.ToolRequest(
            contract_version="v2",
            tool_name=workflow_contracts.models.ToolName.GET_WEEKLY_PROGRESS,
        )


def test_thread_id_uses_unambiguous_component_encoding(workflow_contracts):
    left = workflow_contracts.identity.derive_thread_id("account", "session:one", "v1")
    right = workflow_contracts.identity.derive_thread_id("account:session", "one", "v1")

    assert left != right


def test_workflow_state_validates_request_and_legacy_fields(workflow_contracts):
    with pytest.raises(ValueError):
        workflow_contracts.state.bootstrap_workflow_state(
            account_id="account-1",
            mas_session_id="mas-session-123",
            request_id="not valid!",
            workflow_version="v1",
            legacy_compat={
                "legacy_compat": {
                    "legacy_turn_index": 6,
                    "legacy_session_status": "active",
                }
            },
        )

    with pytest.raises(ValueError):
        workflow_contracts.state.LegacyCompatStateAdapter.bootstrap(
            legacy_turn_index=16,
            legacy_session_status="unknown",
        )


def test_workflow_session_ownership_service_queries_active_mas_session(workflow_contracts):
    expected = SimpleNamespace(
        id="mas-session-123",
        account_id="account-1",
        type="MAS",
        completed=0,
        deleted=0,
    )
    calls = []

    class Query:
        def filter_by(self, **kwargs):
            calls.append(kwargs)
            return self

        def first(self):
            return expected

    class DB:
        def query(self, model):
            calls.append(model)
            return Query()

    service = workflow_contracts.identity.WorkflowSessionOwnershipService(
        DB(), session_model="message_session"
    )
    assert service.get_owned_active_mas_session("account-1", "mas-session-123") is expected
    assert calls == [
        "message_session",
        {
            "id": "mas-session-123",
            "account_id": "account-1",
            "type": "MAS",
            "completed": 0,
            "deleted": 0,
        },
    ]


@pytest.mark.parametrize(
    ("scenario", "error_name", "expected_fields"),
    [
        ("http", "MASGatewayHTTPError", {"status_code": 503}),
        ("timeout", "MASGatewayTimeoutError", {"timeout_seconds": 120.0}),
        ("transport", "MASGatewayTransportError", {"cause_type": "ConnectError"}),
        ("json", "MASGatewayUnexpectedError", {"cause_type": "ValueError"}),
    ],
)
def test_gateway_maps_real_client_failures_to_typed_errors(
    monkeypatch, workflow_contracts, scenario, error_name, expected_fields
):
    monkeypatch.setenv("DATABASE_URL", "sqlite:///:memory:")
    monkeypatch.setenv("SQL_ECHO", "false")
    monkeypatch.setenv("TOKEN_SECRET", "test-secret")
    monkeypatch.setenv("TOKEN_EXPIRE_TIME", "3600")
    module = import_server_module(monkeypatch, "app.services.mas.mas_gateway_service")
    if not hasattr(module.httpx, "Timeout"):
        module = importlib.reload(module)

    class JsonFailureResponse:
        def raise_for_status(self):
            return None

        def json(self):
            raise ValueError("invalid JSON")

    class FakeAsyncClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def post(self, url, json):
            request = module.httpx.Request("POST", url)
            if scenario == "http":
                response = module.httpx.Response(503, request=request, text="unavailable")
                raise module.httpx.HTTPStatusError("unavailable", request=request, response=response)
            if scenario == "timeout":
                raise module.httpx.ReadTimeout("slow", request=request)
            if scenario == "transport":
                raise module.httpx.ConnectError("offline", request=request)
            return JsonFailureResponse()

    monkeypatch.setattr(module.httpx, "AsyncClient", FakeAsyncClient)
    error_type = getattr(workflow_contracts.errors, error_name)

    with pytest.raises(error_type) as captured:
        asyncio.run(module.MASGatewayService.call_mas_service("mma", "/decision"))

    error = captured.value
    assert error.service_name == "mma"
    assert error.endpoint == "/decision"
    for field, expected in expected_fields.items():
        assert getattr(error, field) == expected
