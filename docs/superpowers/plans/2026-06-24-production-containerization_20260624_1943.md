# Production Containerization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Package the FastAPI backend and six MAS services as a CPU-first production Docker Compose stack with optional NVIDIA GPU access, Neon persistence, and no committed secrets.

**Architecture:** The root Compose file builds one backend image and the six existing MAS images on a private network. Only the backend binds to the host; it calls MAS by Docker DNS, loads a server-only environment file, persists generated files in a named volume, and bind-mounts Whisper weights read-only.

**Tech Stack:** Docker Compose v2, Python 3.10, FastAPI/Uvicorn, Neon PostgreSQL, optional NVIDIA Container Toolkit, Python unittest/pytest.

---

### Task 1: Define deployment contracts

**Files:**
- Create: `talkieai-server/tests/test_production_container_config.py`

- [ ] **Step 1: Write failing tests**

Create a `unittest.TestCase` that reads repository files and checks the backend Dockerfile, Compose topology, health checks, restart policy, private MAS ports, GPU override scope, ignored production secrets, and inert environment placeholders.

```python
def test_backend_dockerfile_runs_uvicorn(self):
    dockerfile = self.read("talkieai-server/Dockerfile")
    self.assertIn("FROM python:3.10-slim", dockerfile)
    self.assertIn('CMD ["uvicorn", "app.main:app"', dockerfile)

def test_compose_uses_private_mas_services(self):
    compose = self.read("docker-compose.prod.yml")
    self.assertIn("MAS_MMA_URL: http://mma:8000", compose)
    self.assertIn("condition: service_healthy", compose)
```

- [ ] **Step 2: Verify RED**

Run `python talkieai-server/tests/test_production_container_config.py -v`.

Expected: FAIL because the deployment files do not exist.

- [ ] **Step 3: Commit**

```powershell
git add talkieai-server/tests/test_production_container_config.py
git commit -m "test: define production container contracts"
```

### Task 2: Add the backend image and production environment

**Files:**
- Create: `talkieai-server/Dockerfile`
- Create: `talkieai-server/.dockerignore`
- Create: `talkieai-server/.env.production.example`
- Modify: `.gitignore`

- [ ] **Step 1: Create the image**

Use Python 3.10 slim; install `ffmpeg`, `libsndfile1`, and `libgomp1`; install requirements before copying source; expose 8098; and use:

```dockerfile
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8098"]
```

- [ ] **Step 2: Exclude private and large files**

Exclude `.env*` except examples, virtual environments, caches, Git metadata, tests, logs, uploads, generated files, and both Whisper model directories.

- [ ] **Step 3: Add safe production variables**

```dotenv
DATABASE_URL=postgresql+psycopg2://USER:PASSWORD@HOST/neondb?sslmode=require
AI_SERVER=ZHIPU
ZHIPU_AI_API_KEY=replace-with-rotated-production-key
TOKEN_SECRET=replace-with-random-256-bit-secret
TEMP_SAVE_FILE_PATH=/app/files
WHISPER_MODEL_PATH=/models/whisper
MAS_MEMORY_REQUIRE_DATABASE=true
```

Include existing AI, token, timeout, timezone, Azure, and model settings with safe defaults. Ignore `/talkieai-server/.env.production` in Git.

- [ ] **Step 4: Run focused tests**

Expected: image and secret-isolation assertions pass while Compose assertions remain red.

- [ ] **Step 5: Commit**

```powershell
git add .gitignore talkieai-server/Dockerfile talkieai-server/.dockerignore talkieai-server/.env.production.example
git commit -m "build: add production backend image"
```

### Task 3: Add CPU and GPU Compose definitions

**Files:**
- Create: `docker-compose.prod.yml`
- Create: `docker-compose.gpu.yml`
- Modify: `talkieai-server/tests/test_production_container_config.py`

- [ ] **Step 1: Define the CPU stack**

Create `backend`, `mma`, `soa`, `gra`, `sca`, `ssa`, and `oa`. Every service loads `./talkieai-server/.env.production`, uses `restart: unless-stopped`, joins private `app-network`, and probes `/openapi.json` with Python `urllib.request`.

Publish only `127.0.0.1:8098:8098`. Set backend URLs from `MAS_MMA_URL: http://mma:8000` through `MAS_OA_URL: http://oa:8000`, require database memory, and wait for healthy MAS services. Override MAS entrypoints to run Uvicorn directly, mount `mas/common` read-only, and publish no MAS ports.

Mount `backend-files:/app/files` and `${WHISPER_MODEL_HOST_PATH:-./talkieai-server/mas/whisper-medium-sing2eng-translate}:/models/whisper:ro`.

- [ ] **Step 2: Define the GPU override**

```yaml
services:
  backend:
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: 1
              capabilities: [gpu]
```

- [ ] **Step 3: Verify GREEN**

Run `python talkieai-server/tests/test_production_container_config.py -v`.

Expected: all deployment contract tests pass.

- [ ] **Step 4: Validate Compose**

Create ignored `talkieai-server/.env.production` from the existing local environment without printing secrets. Run CPU and CPU-plus-GPU `docker compose ... config --quiet`; both must exit 0.

- [ ] **Step 5: Commit**

```powershell
git add docker-compose.prod.yml docker-compose.gpu.yml talkieai-server/tests/test_production_container_config.py
git commit -m "build: add production compose stack"
```

### Task 4: Verify the stack end to end

**Files:**
- Verify: `talkieai-server/Dockerfile`
- Verify: `docker-compose.prod.yml`
- Verify: `docker-compose.gpu.yml`

- [ ] **Step 1: Build**

Run `docker compose --env-file talkieai-server/.env.production -f docker-compose.prod.yml build backend`.

Expected: exit 0 without secrets, models, or virtual environments in the context.

- [ ] **Step 2: Start CPU services**

Run `docker compose --env-file talkieai-server/.env.production -f docker-compose.prod.yml up -d --build`.

Expected: seven services start without NVIDIA tooling.

- [ ] **Step 3: Verify health and DNS**

Use `docker compose ... ps` and execute a Python URL probe from backend to each `http://<mas>:8000/openapi.json`.

Expected: all seven services are healthy and all six MAS probes exit 0.

- [ ] **Step 4: Verify external dependencies**

Request backend `/openapi.json`, run `SELECT 1` in backend and one MAS container through configured `DATABASE_URL`, and send one minimal provider request when quota is available. Report only non-secret status summaries.

- [ ] **Step 5: Run regression and hygiene checks**

```powershell
python -m pytest -q talkieai-server/tests/test_db_engine_config.py talkieai-server/tests/test_mas_memory_store.py
python talkieai-server/tests/test_production_container_config.py -v
git check-ignore -v talkieai-server/.env.production talkieai-server/.env talkieai-server/mas/whisper-medium-sing2eng-translate
git diff --check
```

Expected: tests and hygiene checks pass, with no secrets or unrelated files in the diff.
