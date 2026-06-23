import json
import os
from datetime import datetime
from pathlib import Path

from sqlalchemy import (
    Column,
    DateTime,
    MetaData,
    String,
    Table,
    Text,
    create_engine,
    inspect,
    select,
)
from sqlalchemy.exc import IntegrityError, SQLAlchemyError


_ENGINE_CACHE = {}
_SCHEMA_READY = set()
_METADATA = MetaData()
_MEMORY_TABLE = Table(
    "mas_memory_store",
    _METADATA,
    Column("memory_key", String(160), primary_key=True),
    Column("service_name", String(40), nullable=False),
    Column("document_name", String(80), nullable=False),
    Column("payload", Text, nullable=False),
    Column("create_time", DateTime, default=datetime.utcnow),
    Column("update_time", DateTime, default=datetime.utcnow, onupdate=datetime.utcnow),
)


def normalize_database_url(database_url):
    if database_url.startswith("postgres://"):
        return "postgresql+psycopg2://" + database_url[len("postgres://") :]
    if database_url.startswith("postgresql://"):
        return "postgresql+psycopg2://" + database_url[len("postgresql://") :]
    return database_url


def reset_engine_cache():
    for engine in _ENGINE_CACHE.values():
        engine.dispose()
    _ENGINE_CACHE.clear()
    _SCHEMA_READY.clear()


def _database_url():
    raw = os.getenv("DATABASE_URL")
    if not raw:
        if os.getenv("MAS_MEMORY_REQUIRE_DATABASE", "").lower() == "true":
            raise RuntimeError("DATABASE_URL is required for MAS memory persistence")
        return None
    cleaned = raw.strip().strip("'").strip('"')
    if not cleaned:
        if os.getenv("MAS_MEMORY_REQUIRE_DATABASE", "").lower() == "true":
            raise RuntimeError("DATABASE_URL is required for MAS memory persistence")
        return None
    return normalize_database_url(cleaned)


def _engine_options(database_url):
    if database_url.startswith("sqlite"):
        return {"connect_args": {"check_same_thread": False}}
    return {
        "pool_pre_ping": True,
        "pool_size": 5,
        "max_overflow": 5,
        "pool_recycle": 1800,
    }


def _get_engine():
    database_url = _database_url()
    if not database_url:
        return None
    if database_url not in _ENGINE_CACHE:
        engine = create_engine(database_url, **_engine_options(database_url))
        _ENGINE_CACHE[database_url] = engine
    engine = _ENGINE_CACHE[database_url]
    if database_url not in _SCHEMA_READY:
        try:
            _METADATA.create_all(engine)
        except SQLAlchemyError:
            if not inspect(engine).has_table("mas_memory_store"):
                raise
        _SCHEMA_READY.add(database_url)
    return engine


def _memory_key(service_name, document_name):
    return "{}:{}".format(service_name, document_name)


def _read_file(fallback_path, default):
    path = Path(fallback_path)
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except ValueError:
        print("Warning: {} is not valid JSON. Returning default.".format(path), flush=True)
        return default


def _write_file(fallback_path, payload):
    path = Path(fallback_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def load_json(service_name, document_name, default, fallback_path=None):
    engine = _get_engine()
    if engine is None:
        if fallback_path is None:
            return default
        return _read_file(fallback_path, default)

    key = _memory_key(service_name, document_name)
    stmt = select(_MEMORY_TABLE.c.payload).where(_MEMORY_TABLE.c.memory_key == key)
    with engine.connect() as conn:
        row = conn.execute(stmt).fetchone()
    if not row:
        return default
    try:
        return json.loads(row[0])
    except ValueError:
        print("Warning: MAS memory payload {} is not valid JSON.".format(key), flush=True)
        return default


def save_json(service_name, document_name, payload, fallback_path=None):
    engine = _get_engine()
    if engine is None:
        if fallback_path is None:
            raise RuntimeError("fallback_path is required when DATABASE_URL is not set")
        _write_file(fallback_path, payload)
        return

    key = _memory_key(service_name, document_name)
    now = datetime.utcnow()
    payload_text = json.dumps(payload, separators=(",", ":"))
    with engine.begin() as conn:
        if engine.dialect.name == "postgresql":
            from sqlalchemy.dialects.postgresql import insert

            stmt = insert(_MEMORY_TABLE).values(
                memory_key=key,
                service_name=service_name,
                document_name=document_name,
                payload=payload_text,
                create_time=now,
                update_time=now,
            )
            conn.execute(
                stmt.on_conflict_do_update(
                    index_elements=[_MEMORY_TABLE.c.memory_key],
                    set_={
                        "service_name": service_name,
                        "document_name": document_name,
                        "payload": payload_text,
                        "update_time": now,
                    },
                )
            )
        else:
            try:
                conn.execute(
                    _MEMORY_TABLE.insert().values(
                        memory_key=key,
                        service_name=service_name,
                        document_name=document_name,
                        payload=payload_text,
                        create_time=now,
                        update_time=now,
                    )
                )
            except IntegrityError:
                conn.execute(
                    _MEMORY_TABLE.update()
                    .where(_MEMORY_TABLE.c.memory_key == key)
                    .values(
                        service_name=service_name,
                        document_name=document_name,
                        payload=payload_text,
                        update_time=now,
                    )
                )


def memory_exists(service_name, document_name, fallback_path=None):
    engine = _get_engine()
    if engine is None:
        return bool(fallback_path and Path(fallback_path).exists())

    key = _memory_key(service_name, document_name)
    with engine.connect() as conn:
        row = conn.execute(
            select(_MEMORY_TABLE.c.memory_key).where(_MEMORY_TABLE.c.memory_key == key)
        ).fetchone()
    return row is not None
