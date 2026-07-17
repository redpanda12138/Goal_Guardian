"""Isolated, opt-in PostgreSQL checkpointer probe for a future MAS workflow.

This module is deliberately not imported by production MAS routes.  It verifies
the external checkpointer lifecycle before any production workflow migration.
"""
from typing import Any, Awaitable, Callable, Dict, Optional
from urllib.parse import SplitResult, urlsplit, urlunsplit


SUPPORTED_POSTGRES_SCHEMES = {
    "postgresql",
    "postgresql+psycopg",
    "postgresql+psycopg2",
}


class CheckpointProbeConfigurationError(ValueError):
    """Raised without echoing a potentially credential-bearing connection URI."""


def _parse_supported_postgres_uri(connection_uri: str) -> SplitResult:
    if not isinstance(connection_uri, str) or not connection_uri.strip():
        raise CheckpointProbeConfigurationError("A PostgreSQL connection URI is required")
    try:
        parsed = urlsplit(connection_uri)
    except ValueError as error:
        raise CheckpointProbeConfigurationError("The PostgreSQL connection URI is malformed") from error
    if parsed.scheme not in SUPPORTED_POSTGRES_SCHEMES or not parsed.netloc:
        raise CheckpointProbeConfigurationError("A PostgreSQL connection URI is required")
    return parsed


def normalize_checkpoint_postgres_uri(connection_uri: str) -> str:
    """Convert supported SQLAlchemy PostgreSQL URIs to Psycopg 3's URI scheme.

    The returned value is intended only for ``AsyncPostgresSaver``.  Callers
    must use :func:`redact_checkpoint_postgres_uri` before displaying it.
    """
    parsed = _parse_supported_postgres_uri(connection_uri)
    return urlunsplit(("postgresql", parsed.netloc, parsed.path, parsed.query, ""))


def redact_checkpoint_postgres_uri(connection_uri: str) -> str:
    """Return a display-safe URI which replaces a password with ``***``."""
    parsed = _parse_supported_postgres_uri(connection_uri)
    if "@" not in parsed.netloc:
        return urlunsplit((parsed.scheme, parsed.netloc, parsed.path, parsed.query, ""))
    credentials, host = parsed.netloc.rsplit("@", 1)
    username = credentials.split(":", 1)[0]
    redacted_netloc = username + ":***@" + host if ":" in credentials else credentials + "@" + host
    return urlunsplit((parsed.scheme, redacted_netloc, parsed.path, parsed.query, ""))


def _get_async_postgres_saver_factory() -> Any:
    """Import the optional probe dependency only when the probe is explicitly run."""
    try:
        from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
    except ImportError as error:
        raise RuntimeError(
            "Install the isolated checkpoint probe requirements before running this probe"
        ) from error
    return AsyncPostgresSaver


async def run_checkpoint_recovery_probe(
    connection_uri: str,
    thread_id: str,
    *,
    write_checkpoint: Callable[[Any, Dict[str, Dict[str, str]]], Awaitable[None]],
    read_checkpoint: Callable[[Any, Dict[str, Dict[str, str]]], Awaitable[Any]],
    saver_factory: Optional[Any] = None,
) -> Any:
    """Write once, close, then reconstruct the saver and read the same thread.

    LangGraph's official PostgreSQL reference requires ``AsyncPostgresSaver``
    through ``from_conn_string`` and an awaited first ``setup()`` call:
    https://reference.langchain.com/python/langgraph.checkpoint.postgres/
    Thread checkpointing is keyed by ``thread_id`` as documented at:
    https://reference.langchain.com/python/langgraph/checkpoints/
    """
    if not isinstance(thread_id, str) or not thread_id:
        raise CheckpointProbeConfigurationError("A non-empty checkpoint thread_id is required")

    normalized_uri = normalize_checkpoint_postgres_uri(connection_uri)
    factory = saver_factory or _get_async_postgres_saver_factory()
    # Version 1.0.9's direct ``aput`` implementation requires this namespace
    # key even for the default namespace.
    config = {"configurable": {"thread_id": thread_id, "checkpoint_ns": ""}}

    # ``setup`` is intentionally awaited only for the initial saver lifecycle.
    async with factory.from_conn_string(normalized_uri) as initial_saver:
        await initial_saver.setup()
        await write_checkpoint(initial_saver, config)

    async with factory.from_conn_string(normalized_uri) as reopened_saver:
        return await read_checkpoint(reopened_saver, config)
