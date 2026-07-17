# Isolated LangGraph PostgreSQL Checkpoint Probe

## Scope

This document records the Task 1.4 compatibility probe for a possible future MAS workflow migration. The probe is intentionally isolated in `app/services/mas/checkpoint_probe.py`; no MAS production route imports or invokes it. It is not a production database migration and it does not establish a persistent production checkpointer.

## Selected compatible versions

The following optional probe set was selected after an `pip install --dry-run` resolver check in the project Python 3.11 virtual environment:

```text
langchain-core==0.2.43
langgraph==0.2.28
langgraph-checkpoint==1.0.12
langgraph-checkpoint-postgres==1.0.9
psycopg[binary,pool]==3.2.3
psycopg-binary==3.2.3
psycopg-pool==3.2.3
```

The resolver retained the fixed application stack without upgrading it:

```text
FastAPI==0.109.0
Pydantic==1.10.5
SQLAlchemy==2.0.10
httpx==0.25.0
psycopg2-binary==2.9.9
```

The independently installable pins are stored in `requirements-mas-checkpoint-probe.txt`. They are deliberately separate from `requirements.txt` so the unintegrated probe cannot alter the deployed MAS dependency set.

The exact `langgraph-checkpoint-postgres==1.0.9` wheel was inspected without installing it into the application environment. It provides `AsyncPostgresSaver.from_conn_string`, asynchronous `setup`, `aput`, and `aget`. Its direct `aput` implementation requires an explicit default `checkpoint_ns`, which the probe supplies. This prevents newer-version assumptions from being applied to the selected compatibility set.

`langgraph==1.2.9` and `langgraph-checkpoint-postgres==3.1.0` were rejected: their dry-run resolver result required Pydantic 2 and a newer HTTPX release, conflicting with the fixed application stack. The selected 0.2/1.0 series is therefore an older compatibility choice. It should be re-evaluated before any production adoption, and implementation must use only APIs verified for these pins rather than newer LangGraph features.

## Connection strategy and credential handling

The probe accepts only PostgreSQL URIs. It converts the application’s SQLAlchemy forms `postgresql+psycopg2://...` and `postgresql+psycopg://...` to the Psycopg 3 form `postgresql://...`; other database schemes are rejected. The raw URI is passed only to `AsyncPostgresSaver.from_conn_string`. It is never included in error messages, and the supplied redaction helper must be used for display or diagnostics.

The lifecycle follows the official LangGraph references:

- [Checkpointing overview](https://reference.langchain.com/python/langgraph/checkpoints/) specifies that checkpoint history is associated with a `thread_id`.
- [PostgreSQL checkpointer reference](https://reference.langchain.com/python/langgraph.checkpoint.postgres/) documents `AsyncPostgresSaver`, `from_conn_string`, and the first awaited `setup()` call.

The isolated test writes a checkpoint for one `thread_id`, closes the first checkpointer context, creates a new checkpointer context, then reads that same `thread_id`. No production MAS route participates in this operation.

## Real PostgreSQL acceptance boundary

The real recovery test runs only when `MAS_CHECKPOINT_TEST_DATABASE_URL` is explicitly set. It does not load `.env`, inspect `DATABASE_URL`, or change any external database by default. With the special variable absent it skips, which is the expected safe default.

At the time of this record, `MAS_CHECKPOINT_TEST_DATABASE_URL` was unset, `psql` was unavailable, and Docker Desktop’s CLI could not connect to its Linux engine. Consequently, a real PostgreSQL recovery acceptance run was not completed and no successful external-database claim is made.
