import asyncio
import os
from unittest.mock import patch

import pytest

os.environ.setdefault("SQL_ECHO", "false")
os.environ.setdefault("TOKEN_EXPIRE_TIME", "3600")
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")

from app.services.mas.oa_graph_seam import OAGraphRoutingError, route_if_latched_graph, stable_graph_request_id


class Gateway:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    async def call_mas_service(self, service, endpoint, **kwargs):
        self.calls.append((service, endpoint, kwargs))
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response


def run(coro):
    return asyncio.run(coro)


def test_flag_off_preserves_exact_legacy_path_without_oa_call():
    gateway = Gateway([])
    with patch("app.services.mas.oa_graph_seam.Config.MAS_OA_GRAPH_SEAM_ENABLED", False):
        assert run(route_if_latched_graph(gateway, "p", "hello", 6, "r")) is None
    assert gateway.calls == []


def test_graph_mode_uses_latched_generation_and_only_oa_ingress():
    gateway = Gateway([
        {"status": "ok", "workflow_mode": "graph_v1", "workflow_version": "oa_graph_v1", "session_generation": 7},
        {"status": "ok", "selected_agent": "GRA", "message": "duplicate_ignored"},
    ])
    with patch("app.services.mas.oa_graph_seam.Config.MAS_OA_GRAPH_SEAM_ENABLED", True):
        result = run(route_if_latched_graph(gateway, "p", "hello", 6, "stable"))
    assert result["selected_agent"] == "GRA"
    assert [call[0] for call in gateway.calls] == ["oa", "oa"]
    assert gateway.calls[1][1] == "/graph_v1/user_turn"
    assert gateway.calls[1][2]["data"] == {"patient_id": "p", "user_input": "hello", "turn_index": 6, "request_id": "stable", "session_generation": 7}


def test_latched_graph_continues_when_new_session_rollout_is_off():
    gateway = Gateway([
        {"status": "ok", "workflow_mode": "graph_v1", "workflow_version": "oa_graph_v1", "session_generation": 2},
        {"status": "completed", "selected_agent": None},
    ])
    with patch("app.services.mas.oa_graph_seam.Config.MAS_OA_GRAPH_SEAM_ENABLED", True):
        assert run(route_if_latched_graph(gateway, "p", "last", 15, "r"))["status"] == "completed"


@pytest.mark.parametrize("mode_response", [{}, {"status": "ok", "workflow_mode": "unknown"}, RuntimeError("OA down")])
def test_oa_failure_or_ambiguous_mode_fails_closed_without_agent_fallback(mode_response):
    gateway = Gateway([mode_response])
    with patch("app.services.mas.oa_graph_seam.Config.MAS_OA_GRAPH_SEAM_ENABLED", True):
        with pytest.raises((OAGraphRoutingError, RuntimeError)):
            run(route_if_latched_graph(gateway, "p", "hello", 6, "r"))
    assert len(gateway.calls) == 1 and gateway.calls[0][0] == "oa"


def test_stable_request_id_is_deterministic_and_message_specific():
    first = stable_graph_request_id("a", "s", "m")
    assert first == stable_graph_request_id("a", "s", "m")
    assert first != stable_graph_request_id("a", "s", "m2")
