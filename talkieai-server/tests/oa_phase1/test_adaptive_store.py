from concurrent.futures import ThreadPoolExecutor

import pytest

from mas_memory_store import load_json, reset_engine_cache, update_json


@pytest.fixture
def database(tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "sqlite:///" + str(tmp_path / "adaptive.db"))
    reset_engine_cache()
    yield
    reset_engine_cache()


def test_atomic_updates_preserve_concurrent_writers(database):
    update_json("oa", "adaptive-test", lambda old: {"count": 0})
    with ThreadPoolExecutor(max_workers=4) as pool:
        list(pool.map(lambda _: update_json("oa", "adaptive-test", lambda old: {"count": old["count"] + 1}), range(20)))
    assert load_json("oa", "adaptive-test", {}) == {"count": 20}


def test_failed_validation_does_not_commit(database):
    update_json("oa", "adaptive-test", lambda old: {"revision": 3})

    def invalid(old):
        old["revision"] = 4
        raise ValueError("stale_state")

    with pytest.raises(ValueError, match="stale_state"):
        update_json("oa", "adaptive-test", invalid)
    assert load_json("oa", "adaptive-test", {})["revision"] == 3
