import importlib.util
from pathlib import Path


def load_engine_config_module():
    module_path = (
        Path(__file__).resolve().parents[1] / "app" / "db" / "engine_config.py"
    )
    spec = importlib.util.spec_from_file_location("engine_config_under_test", module_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_normalize_database_url_converts_neon_postgres_scheme_to_psycopg():
    engine_config = load_engine_config_module()
    url = "postgres://user:pass@ep-example.neon.tech/app?sslmode=require"

    assert engine_config.normalize_database_url(url) == (
        "postgresql+psycopg2://user:pass@ep-example.neon.tech/app?sslmode=require"
    )


def test_build_engine_options_uses_small_pool_for_postgres():
    engine_config = load_engine_config_module()

    options = engine_config.build_engine_options(
        "postgresql+psycopg2://user:pass@ep-example.neon.tech/app?sslmode=require",
        echo=False,
    )

    assert options["echo"] is False
    assert options["pool_pre_ping"] is True
    assert options["pool_size"] == 5
    assert options["max_overflow"] == 5
    assert options["pool_recycle"] == 1800


def test_build_engine_options_keeps_mysql_pool_recycle():
    engine_config = load_engine_config_module()

    options = engine_config.build_engine_options(
        "mysql+pymysql://user:pass@localhost:3306/app",
        echo=True,
    )

    assert options["echo"] is True
    assert options["pool_pre_ping"] is True
    assert options["pool_size"] == 10
    assert options["max_overflow"] == 20
    assert options["pool_recycle"] == 360


def test_build_engine_options_handles_sqlite_without_queue_pool_options():
    engine_config = load_engine_config_module()

    options = engine_config.build_engine_options("sqlite:///./app.db", echo=False)

    assert options == {
        "echo": False,
        "connect_args": {"check_same_thread": False},
    }
