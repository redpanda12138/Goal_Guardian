# BLOCKED: LangGraph PostgreSQL Checkpoint Probe

## Security decision

Task 1.4 did not pass and no LangGraph production dependency is approved for GoalGuardian. The earlier dry-run candidate (`langgraph==0.2.28` with `langchain-core==0.2.43`) was rejected after the GitHub security advisory [GHSA-g48c-2wqr-h844](https://github.com/advisories/GHSA-g48c-2wqr-h844) identified affected `langgraph` versions through 1.0.9; the advisory lists 1.0.10 as the patched version.

The current application stack remains fixed at Pydantic 1.10.5 and HTTPX 0.25.0. The current LangGraph releases considered for this work require incompatible upgrades. Therefore no LangGraph version is approved for production under this fixed stack. The separate `requirements-mas-checkpoint-probe.txt` file has been retained only as a BLOCKED record and contains comments only; it cannot install the rejected candidate or any other dependency.

## Retained isolated test utility

`app/services/mas/checkpoint_probe.py` remains unimported by MAS production routes. It is a non-production test utility only, and it must not be interpreted as proof of real framework compatibility or a permission to install LangGraph. It does not connect to a database during ordinary tests.

The utility accepts the PostgreSQL schemes recognised by the project configuration, including legacy `postgres://`, and normalizes them to the Psycopg-style `postgresql://` connection scheme. It accepts `postgresql+psycopg2://` and `postgresql+psycopg://` only for the same isolated normalization purpose; non-PostgreSQL schemes are rejected.

Credentials are never placed in configuration errors. Diagnostic URI redaction masks both a userinfo password and the following case-insensitive query keys: `password`, `pass`, `passwd`, `token`, `access_token`, `api_key`, and `sslpassword`. Non-sensitive query parameters are retained.

The historical interface design followed the official LangGraph references for `thread_id`, `AsyncPostgresSaver`, and first-use setup: [checkpointing overview](https://reference.langchain.com/python/langgraph/checkpoints/) and [PostgreSQL checkpointer reference](https://reference.langchain.com/python/langgraph.checkpoint.postgres/). Those references do not override the security block above.

## No database acceptance claim

The opt-in test requires `MAS_CHECKPOINT_TEST_DATABASE_URL`; it never loads `.env` or reads the application's `DATABASE_URL`. This variable remains unset, `psql` is unavailable, and Docker Desktop's Linux engine is unreachable. No PostgreSQL connection was made, no external database was changed, and no real recovery acceptance result is claimed.
