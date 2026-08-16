import asyncio
import importlib.util
import sys
import types
from pathlib import Path
from types import SimpleNamespace

import pytest


SERVER_ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def ai_helper():
    path = SERVER_ROOT / "mas" / "GRA" / "ai_helper.py"
    spec = importlib.util.spec_from_file_location("gra_tool_ai_helper", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _response(content=None, tool_calls=None):
    return SimpleNamespace(
        choices=[
            SimpleNamespace(
                message=SimpleNamespace(content=content, tool_calls=tool_calls)
            )
        ]
    )


def _tool_call(name, arguments):
    return SimpleNamespace(
        id="call-123",
        function=SimpleNamespace(name=name, arguments=arguments),
    )


@pytest.mark.parametrize("provider", ["OPENAI", "ZHIPU"])
def test_tool_capable_provider_returns_a_normalized_model_message(
    monkeypatch, ai_helper, provider
):
    observed = []

    class Completions:
        def create(self, **kwargs):
            observed.append(kwargs)
            return _response(
                tool_calls=[_tool_call("get_weekly_progress", '{"window":"5"}')]
            )

    client = SimpleNamespace(chat=SimpleNamespace(completions=Completions()))
    monkeypatch.setattr(ai_helper, "AI_SERVER", provider)
    if provider == "OPENAI":
        monkeypatch.setattr(ai_helper, "_get_openai_client", lambda: client)
    else:
        monkeypatch.setattr(ai_helper, "_get_zhipu_client", lambda: client)
        monkeypatch.setattr(ai_helper, "ZHIPU_AI_API_KEY", "test-key")

    tools = [{"type": "function", "function": {"name": "get_weekly_progress"}}]
    message = ai_helper.ask_ai_message(
        [{"role": "user", "content": "How am I doing?"}], tools=tools
    )

    assert message == {
        "content": None,
        "tool_calls": [
            {
                "id": "call-123",
                "function": {
                    "name": "get_weekly_progress",
                    "arguments": '{"window":"5"}',
                },
            }
        ],
    }
    assert observed[0]["tools"] == tools
    assert observed[0]["tool_choice"] == "auto"


def test_plain_provider_reply_uses_the_same_normalized_shape(monkeypatch, ai_helper):
    class Completions:
        def create(self, **_kwargs):
            return _response(content="You completed two goals.", tool_calls=None)

    client = SimpleNamespace(chat=SimpleNamespace(completions=Completions()))
    monkeypatch.setattr(ai_helper, "AI_SERVER", "OPENAI")
    monkeypatch.setattr(ai_helper, "_get_openai_client", lambda: client)

    message = ai_helper.ask_ai_message(
        [{"role": "user", "content": "How am I doing?"}], tools=[]
    )

    assert message == {"content": "You completed two goals.", "tool_calls": []}


def test_graph_gra_returns_model_tool_decision_without_executing_or_persisting_reply(
    monkeypatch,
):
    ai_module = types.ModuleType("ai_helper")
    ai_module.ask_ai = lambda *_args, **_kwargs: "legacy reply"
    ai_module.ask_ai_message = lambda *_args, **_kwargs: {
        "content": None,
        "tool_calls": [
            {
                "id": "call-123",
                "function": {
                    "name": "get_weekly_progress",
                    "arguments": "{}",
                },
            }
        ],
    }
    memory_module = types.ModuleType("mas_memory_store")
    memory_module.load_json = lambda *_args, **_kwargs: []
    memory_module.save_json = lambda *_args, **_kwargs: None
    guard_module = types.ModuleType("prompt_guard")
    guard_module.build_coach_prompt = lambda *_args, **_kwargs: "coach prompt"
    guard_module.safe_coach_reply = lambda response, _fallback: response
    catalog_module = types.ModuleType("tool_catalog")
    catalog_module.openai_tool_catalog = lambda: [
        {"type": "function", "function": {"name": "get_weekly_progress"}}
    ]
    monkeypatch.setitem(sys.modules, "ai_helper", ai_module)
    monkeypatch.setitem(sys.modules, "mas_memory_store", memory_module)
    monkeypatch.setitem(sys.modules, "prompt_guard", guard_module)
    monkeypatch.setitem(sys.modules, "tool_catalog", catalog_module)

    path = SERVER_ROOT / "mas" / "GRA" / "app.py"
    spec = importlib.util.spec_from_file_location("gra_graph_tool_app", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    saved = []
    persisted = []
    monkeypatch.setattr(
        module,
        "load_memory",
        lambda: [
            {
                "patient_id": "patient-1",
                "chat_history": [],
                "smart_goals": ["Walk for 30 minutes"],
                "selected_goal": "Walk for 30 minutes",
            }
        ],
    )
    monkeypatch.setattr(module, "save_message", lambda value: saved.append(value))

    async def persist(_url, payload, label, _patient_id, _turn_index):
        persisted.append((label, payload))
        return True

    monkeypatch.setattr(module, "persist_oa_message", persist)

    result = asyncio.run(
        module._receive_message_locked(
            {
                "patient_id": "patient-1",
                "user_input": "How am I doing this week?",
                "turn_index": 7,
                "workflow_mode": "graph_v1",
            }
        )
    )

    assert result["status"] == "tool_requested"
    assert result["model_message"]["tool_calls"][0]["function"]["name"] == "get_weekly_progress"
    assert [label for label, _payload in persisted] == ["user message"]
    assert saved[0]["chat_history"] == [
        {"role": "user", "content": "How am I doing this week?"}
    ]


def test_gra_continuation_turns_tool_result_into_a_persisted_agent_reply(monkeypatch):
    ai_module = types.ModuleType("ai_helper")
    ai_module.ask_ai = lambda *_args, **_kwargs: "You completed two of three goals this week."
    memory_module = types.ModuleType("mas_memory_store")
    memory_module.load_json = lambda *_args, **_kwargs: []
    memory_module.save_json = lambda *_args, **_kwargs: None
    guard_module = types.ModuleType("prompt_guard")
    guard_module.build_coach_prompt = lambda *_args, **_kwargs: "prompt"
    guard_module.safe_coach_reply = lambda response, _fallback: response
    catalog_module = types.ModuleType("tool_catalog")
    catalog_module.openai_tool_catalog = lambda: []
    monkeypatch.setitem(sys.modules, "ai_helper", ai_module)
    monkeypatch.setitem(sys.modules, "mas_memory_store", memory_module)
    monkeypatch.setitem(sys.modules, "prompt_guard", guard_module)
    monkeypatch.setitem(sys.modules, "tool_catalog", catalog_module)

    path = SERVER_ROOT / "mas" / "GRA" / "app.py"
    spec = importlib.util.spec_from_file_location("gra_tool_continuation_app", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    saved = []
    persisted = []
    monkeypatch.setattr(
        module,
        "load_memory",
        lambda: [{"patient_id": "patient-1", "chat_history": []}],
    )
    monkeypatch.setattr(module, "save_message", lambda value: saved.append(value))

    async def persist(_url, payload, label, _patient_id, _turn_index):
        persisted.append((label, payload))
        return True

    monkeypatch.setattr(module, "persist_oa_message", persist)

    result = asyncio.run(
        module._receive_tool_result_locked(
            {
                "patient_id": "patient-1",
                "turn_index": 8,
                "tool_result": {
                    "contract_version": "v1",
                    "tool_name": "get_weekly_progress",
                    "status": "succeeded",
                    "payload": {"weekly_progress": {"completed": 2, "total": 3}},
                    "error_code": None,
                },
            }
        )
    )

    assert result == {
        "status": "message processed",
        "patient_id": "patient-1",
        "turn_index": 8,
        "assistant_message": "You completed two of three goals this week.",
        "persisted": True,
    }
    assert [label for label, _payload in persisted] == ["assistant message"]
    assert saved[0]["chat_history"][-1] == {
        "role": "assistant",
        "content": "You completed two of three goals this week.",
    }

    rejected = asyncio.run(
        module._receive_tool_result_locked(
            {
                "patient_id": "patient-1",
                "turn_index": 8,
                "tool_result": {
                    "contract_version": "v1",
                    "tool_name": "delete_everything",
                    "status": "succeeded",
                    "payload": {},
                    "error_code": None,
                },
            }
        )
    )
    assert rejected == {"status": "error", "reason": "Invalid ToolResult contract"}
