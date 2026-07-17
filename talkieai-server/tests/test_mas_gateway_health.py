import asyncio
import importlib
import os
import sys
import types
from pathlib import Path


SERVER_ROOT = Path(__file__).resolve().parents[1]
if str(SERVER_ROOT) not in sys.path:
    sys.path.insert(0, str(SERVER_ROOT))


class FakeResponse:
    def __init__(self, status_code):
        self.status_code = status_code


class FakeAsyncClient:
    calls = []

    def __init__(self, *args, **kwargs):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def get(self, url, timeout=5):
        self.calls.append(url)
        if url.endswith("/openapi.json"):
            return FakeResponse(200)
        return FakeResponse(404)


def test_health_check_accepts_openapi_when_service_has_no_health_endpoint(monkeypatch):
    os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
    os.environ.setdefault("SQL_ECHO", "false")
    os.environ.setdefault("TOKEN_SECRET", "test-secret")
    os.environ.setdefault("TOKEN_EXPIRE_TIME", "43200")
    monkeypatch.setitem(sys.modules, "httpx", types.SimpleNamespace(AsyncClient=FakeAsyncClient))
    monkeypatch.setitem(sys.modules, "dotenv", types.SimpleNamespace(load_dotenv=lambda: None))
    monkeypatch.setitem(
        sys.modules,
        "app.config",
        types.SimpleNamespace(
            Config=types.SimpleNamespace(
                MAS_MMA_URL="http://mma:8000",
                MAS_SOA_URL="http://soa:8000",
                MAS_GRA_URL="http://gra:8000",
                MAS_SCA_URL="http://sca:8000",
                MAS_SSA_URL="http://ssa:8000",
                MAS_OA_URL="http://oa:8000",
                MAS_HTTP_READ_TIMEOUT=120,
                MAS_HTTP_CONNECT_TIMEOUT=10,
            )
        ),
    )
    monkeypatch.setitem(
        sys.modules,
        "app.core.logging",
        types.SimpleNamespace(logging=types.SimpleNamespace(error=lambda *args, **kwargs: None)),
    )

    module = importlib.import_module("app.services.mas.mas_gateway_service")
    monkeypatch.setattr(module.httpx, "AsyncClient", FakeAsyncClient)
    monkeypatch.setattr(
        module.MASGatewayService,
        "_get_services",
        staticmethod(lambda: {"mma": "http://mma:8000"}),
    )
    FakeAsyncClient.calls = []

    result = asyncio.run(module.MASGatewayService.check_service_health("mma"))

    assert result is True
    assert FakeAsyncClient.calls == [
        "http://mma:8000/health",
        "http://mma:8000/openapi.json",
    ]
