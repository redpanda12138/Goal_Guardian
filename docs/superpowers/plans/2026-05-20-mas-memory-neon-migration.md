# MAS Memory Neon Migration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move MAS memory JSON persistence from local files to the same `DATABASE_URL` database used by the main backend.

**Architecture:** Add a shared MAS memory store that exposes JSON-file-like helpers backed by a `mas_memory_store` SQL table when `DATABASE_URL` is present, with file fallback for local development. Refactor MMA, OA, SOA, GRA, SCA, and SSA to use the helper instead of direct `open/json.load/json.dump`.

**Tech Stack:** Python, FastAPI, SQLAlchemy Core, Postgres/Neon via `psycopg2-binary`, existing MAS microservices.

---

### Task 1: Shared MAS Memory Store

**Files:**
- Create: `talkieai-server/mas/common/mas_memory_store.py`
- Create: `talkieai-server/mas/common/__init__.py`
- Test: `talkieai-server/tests/test_mas_memory_store.py`

- [ ] Write tests for key normalization, DB URL normalization, fallback file behavior, and upsert/load semantics.
- [ ] Implement `load_json`, `save_json`, `append_json`, and `load_all_json` helpers.
- [ ] Use one table: `mas_memory_store(memory_key, service_name, document_name, payload, create_time, update_time)`.

### Task 2: Refactor MAS Agents

**Files:**
- Modify: `talkieai-server/mas/MMA/app.py`
- Modify: `talkieai-server/mas/OA/app.py`
- Modify: `talkieai-server/mas/SOA/app.py`
- Modify: `talkieai-server/mas/GRA/app.py`
- Modify: `talkieai-server/mas/SCA/app.py`
- Modify: `talkieai-server/mas/SSA/app.py`

- [ ] Replace direct JSON memory file reads/writes with the shared helper.
- [ ] Preserve response payload shapes and existing in-memory merge behavior.
- [ ] Keep local file fallback when `DATABASE_URL` is absent.

### Task 3: Runtime Wiring

**Files:**
- Modify: `talkieai-server/mas/docker-compose.yml`
- Modify: each MAS service `requirements.txt`

- [ ] Pass `DATABASE_URL` into every MAS container.
- [ ] Mount or copy the shared `common` helper into every MAS container.
- [ ] Add SQLAlchemy and `psycopg2-binary` to MAS service requirements.

### Task 4: Verification and Review

- [ ] Run MAS storage tests.
- [ ] Run existing backend tests.
- [ ] Run targeted syntax/import checks for each MAS app.
- [ ] Dispatch a review subagent to inspect the diff.
- [ ] Address actionable review findings.
