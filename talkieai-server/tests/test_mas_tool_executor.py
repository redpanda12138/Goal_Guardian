import asyncio
import importlib
import sys
import types
from pathlib import Path

import pytest


SERVER_ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def tool_runtime(monkeypatch):
    server_app_root = (SERVER_ROOT / "app").resolve()
    loaded_app = sys.modules.get("app")
    loaded_file = Path(getattr(loaded_app, "__file__", "")).resolve()
    if loaded_app is not None and server_app_root not in loaded_file.parents:
        for name in list(sys.modules):
            if name == "app" or name.startswith("app."):
                monkeypatch.delitem(sys.modules, name, raising=False)
    monkeypatch.syspath_prepend(str(SERVER_ROOT))
    models = importlib.import_module("app.models.mas_workflow_models")
    executor = importlib.import_module("app.services.mas.tool_executor")
    return types.SimpleNamespace(models=models, executor=executor)


def test_read_tool_executes_without_confirmation_and_returns_versioned_result(tool_runtime):
    observed = []

    async def get_progress(arguments):
        observed.append(arguments)
        return {"completed": 2, "total": 3, "rate": 66.7}

    request = tool_runtime.models.ToolRequest(
        tool_name=tool_runtime.models.ToolName.GET_WEEKLY_PROGRESS,
        arguments={"window": "5"},
    )
    executor = tool_runtime.executor.MASToolExecutor(
        {tool_runtime.models.ToolName.GET_WEEKLY_PROGRESS: get_progress}
    )

    result = asyncio.run(executor.execute(request))

    assert result.status == tool_runtime.models.ToolResultStatus.SUCCEEDED
    assert result.payload == {"completed": 2, "total": 3, "rate": 66.7}
    assert result.contract_version == "v1"
    assert observed == [{"window": "5"}]


@pytest.mark.parametrize(
    "tool_name,arguments",
    [
        ("mark_goal_complete", {"goal_index": 1}),
        ("reschedule_review", {"date": "2030-07-20T09:00:00+08:00"}),
    ],
)
def test_write_tools_fail_closed_until_the_user_confirms(tool_runtime, tool_name, arguments):
    executed = []

    async def write_tool(validated_arguments):
        executed.append(validated_arguments)
        return {"ok": True}

    enum_name = tool_runtime.models.ToolName(tool_name)
    request = tool_runtime.models.ToolRequest(
        tool_name=enum_name,
        arguments=arguments,
        requires_confirmation=True,
    )
    executor = tool_runtime.executor.MASToolExecutor({enum_name: write_tool})

    result = asyncio.run(executor.execute(request, confirmed=False))

    assert result.status == tool_runtime.models.ToolResultStatus.SKIPPED
    assert result.error_code == "confirmation_required"
    assert executed == []


def test_confirmed_write_executes_with_validated_arguments(tool_runtime):
    observed = []

    async def mark_complete(arguments):
        observed.append(arguments)
        return {"ok": True, "changed": True}

    request = tool_runtime.models.ToolRequest(
        tool_name=tool_runtime.models.ToolName.MARK_GOAL_COMPLETE,
        arguments={"goal_index": 0, "note": "Completed after lunch"},
        requires_confirmation=True,
    )
    executor = tool_runtime.executor.MASToolExecutor(
        {tool_runtime.models.ToolName.MARK_GOAL_COMPLETE: mark_complete}
    )

    result = asyncio.run(executor.execute(request, confirmed=True))

    assert result.status == tool_runtime.models.ToolResultStatus.SUCCEEDED
    assert observed == [{"goal_index": 0, "note": "Completed after lunch"}]


@pytest.mark.parametrize(
    "tool_name,arguments",
    [
        ("get_weekly_progress", {"unexpected": True}),
        ("mark_goal_complete", {"goal_index": True}),
        ("mark_goal_complete", {"goal_index": -1}),
        ("reschedule_review", {"date": "2030-07-20T09:00:00"}),
    ],
)
def test_invalid_tool_arguments_return_a_typed_failure(tool_runtime, tool_name, arguments):
    enum_name = tool_runtime.models.ToolName(tool_name)
    request = tool_runtime.models.ToolRequest(
        tool_name=enum_name,
        arguments=arguments,
        requires_confirmation=enum_name
        in {
            tool_runtime.models.ToolName.MARK_GOAL_COMPLETE,
            tool_runtime.models.ToolName.RESCHEDULE_REVIEW,
        },
    )
    executor = tool_runtime.executor.MASToolExecutor({})

    result = asyncio.run(executor.execute(request, confirmed=True))

    assert result.status == tool_runtime.models.ToolResultStatus.FAILED
    assert result.error_code == "invalid_arguments"
    assert "reason" in result.payload


def test_handler_failure_is_contained_in_the_tool_result(tool_runtime):
    async def unavailable(_arguments):
        raise RuntimeError("database unavailable")

    request = tool_runtime.models.ToolRequest(
        tool_name=tool_runtime.models.ToolName.GET_WEEKLY_PROGRESS,
        arguments={},
    )
    executor = tool_runtime.executor.MASToolExecutor(
        {tool_runtime.models.ToolName.GET_WEEKLY_PROGRESS: unavailable}
    )

    result = asyncio.run(executor.execute(request))

    assert result.status == tool_runtime.models.ToolResultStatus.FAILED
    assert result.error_code == "tool_execution_failed"
    assert result.payload == {"reason": "tool execution failed"}
    assert "database unavailable" not in result.json()


def test_business_rejection_is_not_reported_as_a_success(tool_runtime):
    async def reject_goal(_arguments):
        return {"ok": False, "changed": False, "reason": "invalid_goal_index"}

    request = tool_runtime.models.ToolRequest(
        tool_name=tool_runtime.models.ToolName.MARK_GOAL_COMPLETE,
        arguments={"goal_index": 99},
        requires_confirmation=True,
    )
    executor = tool_runtime.executor.MASToolExecutor(
        {tool_runtime.models.ToolName.MARK_GOAL_COMPLETE: reject_goal}
    )

    result = asyncio.run(executor.execute(request, confirmed=True))

    assert result.status == tool_runtime.models.ToolResultStatus.FAILED
    assert result.error_code == "tool_rejected"
    assert result.payload == {
        "ok": False,
        "changed": False,
        "reason": "invalid_goal_index",
    }
