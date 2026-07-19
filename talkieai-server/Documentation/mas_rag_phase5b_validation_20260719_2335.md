# MAS RAG Phase 5B Validation

## Scope

This phase connected the approved-source retrieval boundary to GRA for
`graph_v1` sessions. RAG remains disabled by default and the legacy workflow is
unchanged. No production health corpus was added and no live model request was
made.

## Implemented Flow

1. GRA reads `MAS_RAG_ENABLED` and `MAS_RAG_CORPUS_PATH`. The Compose default is
   disabled and points to the existing read-only `mas/common` mount.
2. When enabled, GRA accepts a UTF-8 JSON object containing a non-empty
   `documents` list. The file is limited to 2 MB and every source must pass the
   Phase 5A approval boundary.
3. The current user message is searched with the deterministic bounded
   retriever. No lexical match produces no augmented context.
4. Retrieved excerpts are serialised into a dedicated system message as
   untrusted reference data. The message instructs the provider not to follow
   instructions embedded in retrieved content and to cite a used `source_id`.
5. Retrieval traces accompany both normal replies and model tool requests.
   The main-backend OA seam revalidates contract version, identifiers, score,
   content length, result count, and the `untrusted_data` marker before the
   trace can reach the client response.
6. An enabled missing or invalid corpus triggers the established GRA fallback
   for that turn. It is not silently treated as approved context.

## Verification

- Focused RAG, GRA provider, tool workflow, and OA seam suite: 47 passed.
- Main backend top-level suite: 152 passed, 1 skipped, and 1 existing expected
  failure.
- OA/LangGraph suite: 57 passed.
- `docker compose -f mas/docker-compose.yml config --quiet` succeeded.
- `git diff --check` reported no whitespace errors before commit.

Observed warnings were existing Starlette multipart, SQLAlchemy base, FastAPI
startup-event, and test-client compatibility deprecations.

## Remaining Boundary

The repository still contains no approved production corpus. Lexical retrieval
is an offline prototype seam rather than semantic retrieval, and the prompt
guard reduces but cannot eliminate model prompt-injection risk. Live-provider
tests, corpus governance, source lifecycle management, citation rendering, and
domain-expert review remain required before enabling RAG in a deployed health
coaching environment. These results demonstrate prototype-level technical
validation only and do not establish clinical safety or effectiveness.
