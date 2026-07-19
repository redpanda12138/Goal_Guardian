# MAS Tool Calling Phase 4B Validation

## Scope

This phase connected model-produced function calls to the authenticated tool
execution boundary introduced in Phase 4A. The validation was offline and did
not call a real model, start Docker, or enable graph traffic.

## Implemented Flow

1. A `graph_v1` request explicitly tells GRA that tool-capable generation is
   permitted. Legacy GRA requests continue to use the original text-only path.
2. OpenAI and Zhipu Chat Completions responses are normalised to the same
   `content` and `tool_calls` structure. Tool execution remains outside the
   model adapter.
3. A single model tool call is converted to the versioned `AgentDecision`
   contract. Unknown tools, malformed arguments, empty responses, and multiple
   simultaneous calls fail closed.
4. Read tools execute immediately through an independent, account-scoped
   database session. This avoids interfering with the uncommitted chat message
   transaction.
5. Write tools return a confirmation prompt without execution. The chat
   response includes the validated `ToolRequest` and continuation turn.
6. After authenticated confirmation, the existing execution endpoint runs the
   write and sends the versioned `ToolResult` to GRA.
7. GRA validates the `ToolResult`, treats its payload as untrusted data,
   generates a constrained response, and persists that response through OA.

The function catalogue is shared by the main backend and GRA, preventing schema
drift between model exposure and execution validation.

## Verification

- Main backend top-level suite: 130 passed, 1 skipped, and 1 existing expected
  failure.
- OA/LangGraph suite: 57 passed.
- Tool decision, provider adapter, GRA continuation, graph seam, executor, and
  legacy-routing tests all passed within their respective suites.
- OpenAI and Zhipu provider behaviour was tested with local response fakes; no
  external model request was made.

Observed warnings were existing deprecation warnings for Starlette multipart
imports, SQLAlchemy `declarative_base`, FastAPI startup events, and the OA test
client HTTP compatibility layer.

## Remaining Boundary

The backend now supports the confirmation lifecycle, but the frontend does not
yet render a dedicated confirmation control or call the confirmed execution
endpoint automatically. Live provider compatibility and end-to-end behaviour
must be verified in a controlled deployed environment before this is described
as production-ready Tool Calling. RAG has not been started.
