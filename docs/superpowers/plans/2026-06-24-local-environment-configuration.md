# Local Environment Configuration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox syntax for tracking.

**Goal:** Complete the ignored local environment configuration and verify the backend, MAS services, Neon, ZhipuAI, and Whisper loading.

**Architecture:** Keep the backend in WSL and MAS services in Docker. Both read talkieai-server/.env, use the same Neon URL, and communicate through Docker-published localhost ports.

**Tech Stack:** PowerShell, WSL Ubuntu 22.04, Python/FastAPI, Docker Compose, Neon PostgreSQL, ZhipuAI.

---

### Task 1: Complete Local Variables

**Files:**
- Modify: talkieai-server/.env (ignored secret file)
- Modify: talkieai-server/.env.default (public template only)

- [ ] Confirm required values report only SET, EMPTY, or ABSENT.
- [ ] Add explicit localhost MAS URLs, connection/read timeouts, scheduler flag, timezone, and file path to .env.
- [ ] Generate a 256-bit random TOKEN_SECRET and replace the local development value.
- [ ] Add the same non-secret variable names and safe defaults to .env.default without real credentials.
- [ ] Confirm talkieai-server/.env remains ignored by Git.

### Task 2: Recreate and Verify MAS

**Files:**
- Runtime: talkieai-server/mas/docker-compose.yml

- [ ] Run docker compose up -d --force-recreate from talkieai-server/mas.
- [ ] Confirm all six containers are Up.
- [ ] Confirm ports 8001 through 8006 return HTTP 200 for /openapi.json.
- [ ] Run a Neon write/read/delete round trip from the MMA container.

### Task 3: Verify Main Backend and Internal MAS Access

**Files:**
- Runtime: talkieai-server/app/main.py

- [ ] Start Uvicorn on 127.0.0.1:8098 with the completed .env.
- [ ] Confirm /openapi.json returns HTTP 200.
- [ ] From the backend environment, request each configured MAS /openapi.json endpoint and confirm HTTP 200.

### Task 4: Verify External AI and Whisper Prerequisites

**Files:**
- Runtime: talkieai-server/app/ai/__init__.py
- Runtime: talkieai-server/app/core/whisper_voice.py

- [ ] Instantiate the configured ZhipuAI provider without printing its key.
- [ ] Send one minimal live request and require a non-empty response.
- [ ] Import the Whisper module with a bounded timeout and report model readiness.
- [ ] Do not claim Azure Speech verification when AZURE_KEY is empty.

### Task 5: Regression and Publication

**Files:**
- Verify: talkieai-server/tests/test_db_engine_config.py
- Verify: talkieai-server/tests/test_mas_memory_store.py
- Verify: talkieai-server/tests/test_services_package_import.py
- Verify: talkieai-server/tests/test_schema_index_names.py

- [ ] Run the focused regression tests.
- [ ] Run git diff --check and secret-presence checks.
- [ ] Commit only .env.default and this plan; never stage .env.
- [ ] Push main to origin using the active local proxy port when required.
