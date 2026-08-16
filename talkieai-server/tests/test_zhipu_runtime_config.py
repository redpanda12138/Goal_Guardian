import importlib.util
import sys
import types
from pathlib import Path
from types import SimpleNamespace

import pytest


SERVER_ROOT = Path(__file__).resolve().parents[1]
AGENTS = ("MMA", "SOA", "GRA", "SCA", "SSA")


def _load_helper(agent, monkeypatch):
    monkeypatch.delenv("ZHIPU_AI_MODEL", raising=False)
    path = SERVER_ROOT / "mas" / agent / "ai_helper.py"
    spec = importlib.util.spec_from_file_location(
        f"{agent.lower()}_zhipu_runtime_config", path
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _response(content="ok"):
    return SimpleNamespace(
        choices=[
            SimpleNamespace(
                message=SimpleNamespace(content=content, tool_calls=None)
            )
        ]
    )


@pytest.mark.parametrize("agent", AGENTS)
def test_every_mas_agent_uses_glm_45_air_without_thinking(monkeypatch, agent):
    helper = _load_helper(agent, monkeypatch)
    observed = []

    class Completions:
        def create(self, **kwargs):
            observed.append(kwargs)
            return _response()

    client = SimpleNamespace(chat=SimpleNamespace(completions=Completions()))
    monkeypatch.setattr(helper, "ZHIPU_AI_API_KEY", "test-key")
    if hasattr(helper, "_get_zhipu_client"):
        monkeypatch.setattr(helper, "_get_zhipu_client", lambda: client)
    else:
        zhipu_module = types.ModuleType("zhipuai")
        zhipu_module.ZhipuAI = lambda **_kwargs: client
        monkeypatch.setitem(sys.modules, "zhipuai", zhipu_module)

    helper._ask_zhipu([{"role": "user", "content": "Hello"}])

    assert observed[0]["model"] == "glm-4.5-air"
    assert observed[0]["thinking"] == {"type": "disabled"}


def test_gra_tool_decision_also_disables_thinking(monkeypatch):
    helper = _load_helper("GRA", monkeypatch)
    observed = []

    class Completions:
        def create(self, **kwargs):
            observed.append(kwargs)
            return _response()

    client = SimpleNamespace(chat=SimpleNamespace(completions=Completions()))
    monkeypatch.setattr(helper, "AI_SERVER", "ZHIPU")
    monkeypatch.setattr(helper, "ZHIPU_AI_API_KEY", "test-key")
    monkeypatch.setattr(helper, "_get_zhipu_client", lambda: client)

    helper.ask_ai_message(
        [{"role": "user", "content": "Show my progress"}],
        tools=[{"type": "function", "function": {"name": "progress"}}],
    )

    assert observed[0]["model"] == "glm-4.5-air"
    assert observed[0]["thinking"] == {"type": "disabled"}
