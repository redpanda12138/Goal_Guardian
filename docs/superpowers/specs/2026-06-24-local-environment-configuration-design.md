# Local Environment Configuration Design

## Goal

Complete the local backend environment configuration without exposing secrets,
then verify the FastAPI backend, six MAS services, Neon persistence, and the
selected ZhipuAI provider.

## Runtime Layout

- The main FastAPI backend runs in WSL on port 8098.
- The MAS services run in Docker and expose ports 8001 through 8006.
- Both the backend and MAS services use the same Neon `DATABASE_URL`.
- The backend reaches MAS services through explicit localhost URLs.

## Local Environment Variables

The ignored `talkieai-server/.env` remains the single local source of secrets.
It will explicitly define:

- `DATABASE_URL`
- `AI_SERVER=ZHIPU`
- `ZHIPU_AI_API_KEY`
- `ZHIPU_AI_MODEL`
- `MAS_MMA_URL` through `MAS_OA_URL`
- `MAS_HTTP_CONNECT_TIMEOUT`
- `MAS_HTTP_READ_TIMEOUT`
- `MAS_OA_SCHEDULER_ENABLED`
- `OA_SCHEDULE_TZ`
- `TEMP_SAVE_FILE_PATH`
- `TOKEN_SECRET`
- `SQL_ECHO`

The existing Neon URL and ZhipuAI credentials are preserved. A new random
`TOKEN_SECRET` replaces the development default, invalidating existing local
login tokens.

## Service Addresses

The WSL-hosted backend uses Docker-published localhost ports:

- MMA: `http://localhost:8001`
- SOA: `http://localhost:8002`
- GRA: `http://localhost:8003`
- SCA: `http://localhost:8004`
- SSA: `http://localhost:8005`
- OA: `http://localhost:8006`

These are local-only values. A future production Compose deployment will use
Docker service names instead.

## Secret Handling

- Never print complete environment values.
- Report only `SET`, `EMPTY`, or `ABSENT` for secret variables.
- Keep `.env` ignored by Git.
- Do not place real credentials in `.env.default`, documentation, tests, or
  Docker Compose.

## Verification

1. Validate required variables without printing values.
2. Recreate MAS containers and verify ports 8001-8006 return HTTP 200.
3. Run a Neon write/read/delete round trip through project code.
4. Start the main backend and verify `/openapi.json` returns HTTP 200.
5. Verify backend-to-MAS health access.
6. Perform one minimal live ZhipuAI request.
7. Check that the Whisper module can initialize; report unavailable model or
   audio prerequisites instead of fabricating a successful transcription.
8. Run focused regression tests and verify `.env` remains ignored.

## Non-Goals

- Adding OpenAI credentials or provider failover.
- Containerizing the main backend.
- Creating production environment files.
- Configuring Azure Speech when `AZURE_KEY` is absent.
