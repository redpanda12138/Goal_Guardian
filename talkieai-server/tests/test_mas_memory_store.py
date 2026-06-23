import importlib.util
import json
import os
from pathlib import Path


def load_store_module():
    module_path = (
        Path(__file__).resolve().parents[1]
        / "mas"
        / "common"
        / "mas_memory_store.py"
    )
    spec = importlib.util.spec_from_file_location("mas_memory_store_under_test", module_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_normalize_database_url_supports_neon_postgres_scheme():
    store = load_store_module()

    assert store.normalize_database_url("postgres://u:p@host/db?sslmode=require") == (
        "postgresql+psycopg2://u:p@host/db?sslmode=require"
    )


def test_load_and_save_json_uses_database_when_url_is_set(tmpdir):
    store = load_store_module()
    db_path = Path(str(tmpdir.join("memory.db")))
    fallback_path = Path(str(tmpdir.join("fallback.json")))
    os.environ["DATABASE_URL"] = "sqlite:///" + str(db_path)
    store.reset_engine_cache()

    store.save_json("oa", "goal_reviews", [{"patient_id": "p1"}], fallback_path)
    store.save_json("oa", "goal_reviews", [{"patient_id": "p1"}, {"patient_id": "p2"}], fallback_path)
    loaded = store.load_json("oa", "goal_reviews", [], fallback_path)

    assert loaded == [{"patient_id": "p1"}, {"patient_id": "p2"}]
    assert not fallback_path.exists()

    os.environ.pop("DATABASE_URL", None)
    store.reset_engine_cache()


def test_database_url_can_be_required_for_deployment(monkeypatch):
    store = load_store_module()
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setenv("MAS_MEMORY_REQUIRE_DATABASE", "true")
    store.reset_engine_cache()

    try:
        store.load_json("oa", "goal_reviews", [])
    except RuntimeError as exc:
        assert "DATABASE_URL is required" in str(exc)
    else:
        raise AssertionError("Expected RuntimeError when DATABASE_URL is required")

    store.reset_engine_cache()


def test_load_and_save_json_falls_back_to_file_without_database_url(tmpdir):
    store = load_store_module()
    os.environ.pop("DATABASE_URL", None)
    store.reset_engine_cache()
    fallback_path = Path(str(tmpdir.mkdir("memory").join("goal_reviews.json")))

    store.save_json("oa", "goal_reviews", [{"patient_id": "p2"}], fallback_path)
    loaded = store.load_json("oa", "goal_reviews", [], fallback_path)

    assert loaded == [{"patient_id": "p2"}]
    assert json.loads(fallback_path.read_text()) == [{"patient_id": "p2"}]


def test_load_json_returns_default_for_missing_database_record(tmpdir):
    store = load_store_module()
    os.environ["DATABASE_URL"] = "sqlite:///" + str(tmpdir.join("memory.db"))
    store.reset_engine_cache()

    assert store.load_json("mma", "missing", {"empty": True}) == {"empty": True}

    os.environ.pop("DATABASE_URL", None)
    store.reset_engine_cache()
