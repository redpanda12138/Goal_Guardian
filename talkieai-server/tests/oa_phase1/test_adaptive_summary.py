import pytest

from adaptive_summary import build_summary
from mas_memory_store import load_json, reset_engine_cache


def test_summary_retries_without_duplicate_persistence(tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "sqlite:///" + str(tmp_path / "summary.db"))
    reset_engine_cache()
    data = {"patient_id": "p", "session_generation": 1, "chat_history": [], "review_outcome": "stopped"}
    def failure(*_):
        raise RuntimeError("offline")
    with pytest.raises(RuntimeError):
        build_summary(data, failure)
    assert build_summary(data, lambda *_: "Stopped with items unresolved.")["status"] == "ok"
    assert build_summary(data, failure)["replayed"] is True
    assert len(load_json("ssa", "session_summaries", [])) == 1
    build_summary({**data, "session_generation": 2}, lambda *_: "Second review")
    assert len(load_json("ssa", "session_summaries", [])) == 2
    reset_engine_cache()


def test_uncertain_memory_export_is_reported_without_duplicate_write(tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "sqlite:///" + str(tmp_path / "export.db"))
    reset_engine_cache()
    data = {"patient_id": "p", "session_generation": 1, "chat_history": []}
    calls = []
    def export(_):
        calls.append(1)
        raise RuntimeError("response lost")
    for _ in range(2):
        result = build_summary(data, lambda *_: "Summary", export)
        assert result["status"] == "ok"
        assert result["memory_export_status"] == "indeterminate"
    assert len(calls) == 1
    reset_engine_cache()
