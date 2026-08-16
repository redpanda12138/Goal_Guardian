import asyncio
import importlib
import importlib.util
import sys
import types
from pathlib import Path

import pytest

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
def legacy_routing(monkeypatch):
    return import_server_module(monkeypatch, "app.services.mas.legacy_routing")


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
    turn_index, expected_agent, legacy_routing
):
    assert legacy_routing.select_legacy_mas_agent(turn_index) == expected_agent


def test_legacy_soa_compatibility_response_retries_with_gra_only(legacy_routing):
    assert legacy_routing.should_retry_soa_with_gra(
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
def test_legacy_timeout_or_non_compatibility_result_does_not_retry_with_gra(
    result, legacy_routing
):
    assert not legacy_routing.should_retry_soa_with_gra(result)


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


def test_legacy_gra_turn_12_persists_user_message_then_triggers_sca(
    legacy_gra_module, monkeypatch
):
    persistence_calls = []
    trigger_calls = []

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
        persistence_calls.append((url, label))
        return True

    async def run_blocking(func, *args, **kwargs):
        if func is legacy_gra_module.requests.post:
            trigger_calls.append((args, kwargs))
            return types.SimpleNamespace(status_code=200)
        return "unused"

    monkeypatch.setattr(legacy_gra_module, "persist_oa_message", persist_oa_message)
    monkeypatch.setattr(legacy_gra_module, "run_blocking", run_blocking)
    monkeypatch.setattr(legacy_gra_module, "save_message", lambda _record: None)

    result = asyncio.run(
        legacy_gra_module._receive_message_locked(
            {"patient_id": "patient-1", "user_input": "closing reflection", "turn_index": 12}
        )
    )

    assert result["turn_index"] == 13
    assert persistence_calls == [(legacy_gra_module.OA_USER_URL, "user message")]
    assert trigger_calls[0][0][0] == legacy_gra_module.SCA_URL


def test_chat_service_production_wiring_uses_its_distinct_turn_six_route():
    source = (SERVER_ROOT / "app" / "services" / "chat_service.py").read_text(
        encoding="utf-8"
    )
    assert "selected_agent = select_legacy_mas_agent(current_turn_index)" in source
    assert "if turn_index <= 5:" in (
        SERVER_ROOT / "app" / "services" / "mas" / "legacy_routing.py"
    ).read_text(encoding="utf-8")


def test_api_route_production_wiring_still_sends_turn_six_to_soa():
    source = (SERVER_ROOT / "app" / "api" / "mas_routes.py").read_text(encoding="utf-8")
    assert "if dto.turn_index <= 6:" in source
    assert '"soa"' in source


def test_oa_production_wiring_still_reports_turn_six_as_soa():
    source = (SERVER_ROOT / "mas" / "OA" / "app.py").read_text(encoding="utf-8")
    assert "if turn_index <= 6:" in source
    assert 'current_agent = "SOA"' in source


@pytest.mark.xfail(
    strict=True,
    reason="Known legacy baseline: timeout after a remote commit can retry the same request through another agent and duplicate side effects.",
)
def test_api_route_timeout_does_not_fallback_to_another_agent(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "sqlite:///:memory:")
    monkeypatch.setenv("SQL_ECHO", "false")
    monkeypatch.setenv("TOKEN_SECRET", "test-secret")
    monkeypatch.setenv("TOKEN_EXPIRE_TIME", "3600")
    mas_routes = import_server_module(monkeypatch, "app.api.mas_routes")
    gateway_errors = import_server_module(
        monkeypatch, "app.services.mas.gateway_errors"
    )
    service_calls = []

    async def call_mas_service(service_name, endpoint, **_kwargs):
        service_calls.append(service_name)
        if service_name == "soa":
            raise gateway_errors.MASGatewayTimeoutError(
                service_name,
                endpoint,
                "timeout after remote commit",
                timeout_seconds=120.0,
            )
        return {"status": "ok"}

    monkeypatch.setattr(
        mas_routes,
        "_get_patient_id_and_release_db",
        lambda _db, _account_id: "patient-1",
    )
    monkeypatch.setattr(
        mas_routes.MASGatewayService,
        "call_mas_service",
        staticmethod(call_mas_service),
    )

    asyncio.run(
        mas_routes.send_message(
            mas_routes.SendMessageDTO(user_input="message", turn_index=6),
            db=object(),
            account_id="account-1",
        )
    )

    assert service_calls == ["soa"]
