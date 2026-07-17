import asyncio
import importlib.util
import sys
import types
from pathlib import Path

import pytest

from app.services.mas.legacy_routing import (
    select_legacy_mas_agent,
    should_retry_soa_with_gra,
)


SERVER_ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize(
    ("turn_index", "expected_agent"),
    [
        (1, "soa"),
        (6, "gra"),
        (7, "gra"),
        (13, "gra"),
        (14, "sca"),
        (15, "sca"),
    ],
)
def test_legacy_route_selects_the_existing_agent_at_stage_boundaries(
    turn_index, expected_agent
):
    assert select_legacy_mas_agent(turn_index) == expected_agent


def test_legacy_soa_compatibility_response_retries_with_gra_only():
    assert should_retry_soa_with_gra(
        {"status": "error", "reason": "should be sent to GRA"}
    )


@pytest.mark.parametrize(
    "result",
    [
        None,
        {"status": "error", "reason": "request timeout"},
        {"status": "error", "reason": "SOA unavailable"},
        {"status": "ok", "reason": "should be sent to GRA"},
    ],
)
def test_legacy_timeout_or_non_compatibility_result_does_not_retry_with_gra(result):
    assert not should_retry_soa_with_gra(result)


@pytest.fixture
def legacy_gra_module(monkeypatch):
    ai_helper = types.ModuleType("ai_helper")
    ai_helper.ask_ai = lambda *_args, **_kwargs: "unused"
    memory_store = types.ModuleType("mas_memory_store")
    memory_store.load_json = lambda *_args, **_kwargs: []
    memory_store.save_json = lambda *_args, **_kwargs: None
    prompt_guard = types.ModuleType("prompt_guard")
    prompt_guard.build_coach_prompt = lambda *_args, **_kwargs: "prompt"
    prompt_guard.safe_coach_reply = lambda response, _fallback: response

    monkeypatch.setitem(sys.modules, "ai_helper", ai_helper)
    monkeypatch.setitem(sys.modules, "mas_memory_store", memory_store)
    monkeypatch.setitem(sys.modules, "prompt_guard", prompt_guard)

    module_path = SERVER_ROOT / "mas" / "GRA" / "app.py"
    spec = importlib.util.spec_from_file_location("legacy_gra_app_under_test", module_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_legacy_gra_persists_user_then_assistant_message_to_oa(legacy_gra_module, monkeypatch):
    persistence_calls = []
    saved_records = []

    monkeypatch.setattr(
        legacy_gra_module,
        "load_memory",
        lambda: [
            {
                "patient_id": "patient-1",
                "chat_history": [],
                "selected_goal": "walk daily",
                "smart_goals": ["Walk daily"],
            }
        ],
    )

    async def persist_oa_message(url, payload, label, patient_id, turn_index):
        persistence_calls.append((url, payload, label, patient_id, turn_index))
        return True

    async def run_blocking(*_args, **_kwargs):
        return "assistant reply"

    monkeypatch.setattr(legacy_gra_module, "persist_oa_message", persist_oa_message)
    monkeypatch.setattr(legacy_gra_module, "run_blocking", run_blocking)
    monkeypatch.setattr(legacy_gra_module, "save_message", saved_records.append)

    result = asyncio.run(
        legacy_gra_module._receive_message_locked(
            {"patient_id": "patient-1", "user_input": "I walked", "turn_index": 8}
        )
    )

    assert result["persisted"] is True
    assert [call[2] for call in persistence_calls] == ["user message", "assistant message"]
    assert persistence_calls[0][0] == legacy_gra_module.OA_USER_URL
    assert persistence_calls[1][0] == legacy_gra_module.OA_URL
    assert saved_records[0]["chat_history"] == [
        {"role": "user", "content": "I walked"},
        {"role": "assistant", "content": "assistant reply"},
    ]


def test_legacy_gra_deduplicates_repeated_content_not_request_identifier(
    legacy_gra_module, monkeypatch
):
    persistence_calls = []
    repeated_content = "same message"

    monkeypatch.setattr(
        legacy_gra_module,
        "load_memory",
        lambda: [
            {
                "patient_id": "patient-1",
                "chat_history": [
                    {"role": "user", "content": "earlier-1"},
                    {"role": "user", "content": "earlier-2"},
                    {"role": "user", "content": "earlier-3"},
                    {"role": "user", "content": "earlier-4"},
                    {"role": "user", "content": "earlier-5"},
                    {"role": "user", "content": repeated_content},
                ],
            }
        ],
    )

    async def persist_oa_message(*args, **kwargs):
        persistence_calls.append((args, kwargs))
        return True

    monkeypatch.setattr(legacy_gra_module, "persist_oa_message", persist_oa_message)

    first = asyncio.run(
        legacy_gra_module._receive_message_locked(
            {
                "patient_id": "patient-1",
                "user_input": repeated_content,
                "turn_index": 6,
                "request_id": "request-a",
            }
        )
    )
    second = asyncio.run(
        legacy_gra_module._receive_message_locked(
            {
                "patient_id": "patient-1",
                "user_input": repeated_content,
                "turn_index": 6,
                "request_id": "request-b",
            }
        )
    )

    assert first["status"] == second["status"] == "already_processed"
    assert persistence_calls == []
