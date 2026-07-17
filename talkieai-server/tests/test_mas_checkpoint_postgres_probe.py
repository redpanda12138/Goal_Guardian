import asyncio
import importlib
import os
import sys
from pathlib import Path
from uuid import uuid4

import pytest


SERVER_ROOT = Path(__file__).resolve().parents[1]


def load_probe_module(monkeypatch):
    monkeypatch.syspath_prepend(str(SERVER_ROOT))
    return importlib.import_module("app.services.mas.checkpoint_probe")


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        (
            "postgresql+psycopg2://user:secret@example.test:5432/goalguardian?sslmode=require",
            "postgresql://user:secret@example.test:5432/goalguardian?sslmode=require",
        ),
        (
            "postgresql+psycopg://user:secret@example.test/goalguardian",
            "postgresql://user:secret@example.test/goalguardian",
        ),
        (
            "postgresql://user:secret@example.test/goalguardian",
            "postgresql://user:secret@example.test/goalguardian",
        ),
    ],
)
def test_normalize_checkpoint_uri_converts_supported_sqlalchemy_postgres_schemes(
    monkeypatch, source, expected
):
    probe = load_probe_module(monkeypatch)

    assert probe.normalize_checkpoint_postgres_uri(source) == expected


def test_normalize_checkpoint_uri_rejects_non_postgres_without_leaking_credentials(
    monkeypatch,
):
    probe = load_probe_module(monkeypatch)

    with pytest.raises(probe.CheckpointProbeConfigurationError) as captured:
        probe.normalize_checkpoint_postgres_uri("mysql+pymysql://user:secret@example.test/db")

    assert "secret" not in str(captured.value)
    assert "PostgreSQL" in str(captured.value)


def test_redact_checkpoint_uri_never_exposes_the_password(monkeypatch):
    probe = load_probe_module(monkeypatch)

    assert probe.redact_checkpoint_postgres_uri(
        "postgresql://user:secret@example.test/goalguardian"
    ) == "postgresql://user:***@example.test/goalguardian"


def test_async_probe_initializes_closes_and_recovers_same_thread_checkpoint(monkeypatch):
    probe = load_probe_module(monkeypatch)
    events = []
    stored = {}

    class FakeSaver:
        def __init__(self, name):
            self.name = name

        async def setup(self):
            events.append(f"setup:{self.name}")

        async def aput(self, config, checkpoint, metadata, new_versions):
            events.append(f"write:{self.name}")
            stored[config["configurable"]["thread_id"]] = checkpoint

        async def aget(self, config):
            events.append(f"read:{self.name}")
            return stored.get(config["configurable"]["thread_id"])

    class FakeContextManager:
        def __init__(self, saver):
            self.saver = saver

        async def __aenter__(self):
            events.append(f"open:{self.saver.name}")
            return self.saver

        async def __aexit__(self, exc_type, exc, traceback):
            events.append(f"close:{self.saver.name}")

    class FakeSaverFactory:
        def __init__(self):
            self.names = iter(("first", "reopened"))
            self.connection_uris = []

        def from_conn_string(self, connection_uri):
            self.connection_uris.append(connection_uri)
            return FakeContextManager(FakeSaver(next(self.names)))

    async def write_checkpoint(saver, config):
        assert config == {
            "configurable": {
                "thread_id": "account-session-v1",
                "checkpoint_ns": "",
            }
        }
        checkpoint = {"probe_payload": "persisted"}
        await saver.aput(config, checkpoint, {}, {})

    async def read_checkpoint(saver, config):
        assert config == {
            "configurable": {
                "thread_id": "account-session-v1",
                "checkpoint_ns": "",
            }
        }
        return await saver.aget(config)

    factory = FakeSaverFactory()
    recovered = asyncio.run(
        probe.run_checkpoint_recovery_probe(
            "postgresql+psycopg2://user:secret@example.test/goalguardian",
            "account-session-v1",
            write_checkpoint=write_checkpoint,
            read_checkpoint=read_checkpoint,
            saver_factory=factory,
        )
    )

    assert recovered == {"probe_payload": "persisted"}
    assert factory.connection_uris == [
        "postgresql://user:secret@example.test/goalguardian",
        "postgresql://user:secret@example.test/goalguardian",
    ]
    assert events == [
        "open:first",
        "setup:first",
        "write:first",
        "close:first",
        "open:reopened",
        "read:reopened",
        "close:reopened",
    ]


def test_production_mas_route_does_not_refer_to_checkpoint_probe():
    route_source = (SERVER_ROOT / "app" / "api" / "mas_routes.py").read_text(
        encoding="utf-8"
    )

    assert "checkpoint_probe" not in route_source


def test_real_postgres_checkpoint_recovery_is_opt_in(monkeypatch):
    connection_uri = os.getenv("MAS_CHECKPOINT_TEST_DATABASE_URL")
    if not connection_uri:
        pytest.skip("set MAS_CHECKPOINT_TEST_DATABASE_URL to run the isolated PostgreSQL recovery probe")

    probe = load_probe_module(monkeypatch)
    pytest.importorskip(
        "langgraph.checkpoint.postgres.aio",
        reason="install the isolated checkpoint probe requirements before running the opt-in integration test",
    )
    thread_id = "checkpoint-probe-" + uuid4().hex

    async def write_checkpoint(saver, config):
        await saver.aput(
            config,
            {
                "v": 1,
                "id": uuid4().hex,
                "ts": "2026-07-18T00:00:00+00:00",
                "channel_values": {"probe_payload": "persisted"},
                "channel_versions": {"probe_payload": "1"},
                "versions_seen": {},
                "pending_sends": [],
            },
            {"source": "checkpoint-probe", "step": 1},
            {"probe_payload": "1"},
        )

    async def read_checkpoint(saver, config):
        return await saver.aget(config)

    recovered = asyncio.run(
        probe.run_checkpoint_recovery_probe(
            connection_uri,
            thread_id,
            write_checkpoint=write_checkpoint,
            read_checkpoint=read_checkpoint,
        )
    )

    assert recovered is not None
    assert recovered["channel_values"]["probe_payload"] == "persisted"
