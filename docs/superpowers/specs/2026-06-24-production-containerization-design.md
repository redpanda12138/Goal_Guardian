# Production Containerization Design

## Goal

Package the main FastAPI backend and six MAS services into a production Docker
deployment that runs on a CPU-only Linux server by default and can enable an
NVIDIA GPU through an optional Compose override.

## Architecture

Nginx is the only public entry point and forwards HTTPS traffic to the backend
container on port 8098. The backend and MAS containers share a private Docker
network. The backend reaches MAS services through Compose service names such as
http://mma:8000 instead of published localhost ports.

The backend and all MAS services use the same Neon DATABASE_URL and AI provider
configuration. Only Nginx ports 80 and 443 are public in the final server
layout. The first implementation validates the application stack without
adding Nginx configuration.

## Deployment Files

- talkieai-server/Dockerfile builds the main backend CPU image.
- talkieai-server/.dockerignore excludes secrets, virtual environments,
  generated files, logs, uploads, and Whisper model weights.
- docker-compose.prod.yml defines the backend and six MAS services.
- docker-compose.gpu.yml adds optional NVIDIA GPU access to the backend.
- talkieai-server/.env.production.example documents production variables
  without containing credentials.
- .gitignore excludes talkieai-server/.env.production.

## Backend Image

The backend image uses Python 3.10 to match the existing MAS images and tested
WSL environment. It installs required system audio libraries, installs
talkieai-server/requirements.txt, copies application source, and starts Uvicorn
in the foreground on port 8098.

The image does not contain:

- Neon or AI credentials
- Local virtual environments
- The 5.7 GB Whisper model
- Runtime logs
- Uploaded or generated files

## Whisper Model Strategy

CPU mode is the baseline. The server mounts a model directory read-only at a
stable container path and sets WHISPER_MODEL_PATH to that path.

The optional GPU Compose override requests an NVIDIA device for the backend.
It does not duplicate the base service definition. Servers without the NVIDIA
Container Toolkit use only docker-compose.prod.yml.

Whisper model absence does not prevent chat, MAS, database, or AI features from
starting. Voice transcription reports that the model is unavailable.

## Services and Networking

The production stack contains:

- backend on internal port 8098
- mma, soa, gra, sca, ssa, and oa on internal port 8000

MAS host ports are not published. Backend environment variables use:

- MAS_MMA_URL=http://mma:8000
- MAS_SOA_URL=http://soa:8000
- MAS_GRA_URL=http://gra:8000
- MAS_SCA_URL=http://sca:8000
- MAS_SSA_URL=http://ssa:8000
- MAS_OA_URL=http://oa:8000

Every service uses restart: unless-stopped. Health checks use Python HTTP
requests against each service's OpenAPI endpoint so the slim images do not
need curl.

## Persistence

Neon stores business tables and MAS memory documents. Docker-managed volumes
persist backend uploads and generated files. Whisper weights are a read-only
bind mount from the server. Application logs go to stdout and stderr for Docker
log rotation; existing MAS log directories remain mounted only where required
by current start commands.

## Environment and Secrets

talkieai-server/.env.production exists only on the server and is loaded by
Compose. The tracked example contains placeholders and safe defaults only.
Production uses a new random TOKEN_SECRET and a rotated ZhipuAI key because the
previous key appeared in Git history.

The same environment file supplies Neon and AI settings to the backend and MAS
services. MAS_MEMORY_REQUIRE_DATABASE remains true in production.

## Startup and Failure Handling

MAS services start first and expose health status. The backend starts after the
required MAS health checks pass. OA scheduling is enabled only in the backend
to avoid duplicate scheduled jobs.

- Neon failure affects database-backed requests and is logged.
- MAS failure produces a backend proxy error without stopping unrelated
  services.
- AI quota or provider failure uses the existing AI exception path.
- Missing Whisper weights disables voice transcription only.
- GPU startup failure is avoided by deploying the CPU Compose file without the
  GPU override.

## Verification

The implementation must verify:

1. The backend image builds without copying ignored secrets or models.
2. The production Compose file resolves with the example environment.
3. All seven services become healthy in a local production simulation.
4. The backend reaches all MAS services through Docker service names.
5. Backend and MAS database round trips use Neon.
6. A minimal ZhipuAI request succeeds when credentials have quota.
7. The CPU stack starts without NVIDIA tooling.
8. The GPU override passes Compose configuration validation.
9. Real environment files, model weights, logs, and uploads remain untracked.

## Non-Goals

- Installing or configuring Nginx and TLS on a real server.
- Selecting a cloud provider or server size.
- Splitting Whisper into a separate service.
- Adding an administration platform.
- Rewriting Git history during this implementation.
