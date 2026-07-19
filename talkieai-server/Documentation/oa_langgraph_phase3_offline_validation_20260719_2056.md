# OA LangGraph Phase 3 Offline Validation

## Scope

This record covers the offline portion of Phase 3 for the OA-embedded LangGraph workflow. Live Docker rollout was explicitly skipped. The results therefore demonstrate deterministic routing and resilience behaviour in isolated tests, not deployment readiness or production performance.

## Verified behaviour

- Route parity remained SOA for turns 0–5, GRA for turns 6–13, SCA for turn 14, and terminal with no Agent dispatch at turn 15.
- A restarted OA process reconstructed the latched workflow mode, workflow version, session generation, and request reservations from the existing OA business record without a LangGraph checkpointer.
- A completed request remained idempotent after reconstruction and did not append the user message again.
- A request persisted as `dispatching` remained fail-closed after reconstruction. It was not automatically redispatched because downstream Agents do not expose an idempotency contract.
- An ambiguous downstream timeout transitioned the reservation to `indeterminate`; a retry with the same request identity did not create a second Agent call.
- Disabling `OA_LANGGRAPH_NEW_SESSIONS_ENABLED` left the active graph generation unchanged and assigned `legacy` only after the next atomic session reset.
- Disabling the main-backend seam was not treated as a session rollback mechanism. The seam must remain enabled while graph generations are active.

## Test evidence

- OA Phase 1–3 focused suite: `56 passed`.
- Main-backend seam and legacy routing suite: `24 passed, 1 xfailed`.
- The xfail is the documented legacy timeout baseline in which an ambiguous remote commit can cause duplicate side effects.
- Reported warnings were deprecation or local pytest-cache warnings and did not affect assertions.

## Not verified

- Docker image rebuild and service restart.
- Live OA-to-Agent HTTP dispatch.
- Real model-provider calls.
- Restart recovery across an actual container or host reboot.
- End-to-end latency, throughput, or resource use.

## Result

The offline resilience gate passed. Phase 3 remains partially complete until a controlled environment is available for live rollout and restart verification. No RAG, tool calling, persistent checkpoint, new service, or new database was introduced.
