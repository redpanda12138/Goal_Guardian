# OA-Embedded LangGraph Routing Design

**Status:** Approved architecture for specification; implementation has not started  
**Scope owner:** GoalGuardian MAS Orchestrator Agent (OA)  
**Date:** 18 July 2026

## 1. Decision Summary

GoalGuardian will retain the existing six MAS microservices: MMA, SOA, GRA, SCA, SSA, and OA. A LangGraph release proven compatible with the OA runtime will be embedded inside the existing OA container. LangGraph will act only as an in-memory routing engine. OA will remain the sole business orchestrator and the authoritative owner of session business state.

No new service, database, or persistent LangGraph checkpointer will be introduced. OA will continue to persist business state through its existing MAS memory store. After an OA restart, a graph invocation will be reconstructed from the persisted OA record rather than resumed from a LangGraph checkpoint.

Existing sessions will remain on the legacy workflow. New sessions created while the rollout feature flag is enabled will be assigned to `graph_v1`. The assigned workflow mode is latched for the lifetime of that session and will not change because the environment flag changes later.

The frontend, public backend API, main-backend persistence model, and the five non-OA Agent services will not adopt LangGraph or graph state. Their existing HTTP contracts remain the integration boundary.

## 2. Goals

The design has the following goals:

1. Introduce an explicit, testable workflow-routing graph without changing the six-service deployment topology.
2. Make OA the single authority that selects the next Agent and executes the selected transition.
3. Preserve the observable behavior of the legacy weekly SMART goal review, including its turn boundaries and the narrowly defined SOA-to-GRA compatibility transition.
4. Keep graph execution ephemeral and reconstructable from OA-owned business state.
5. Permit safe, session-level rollout through a default-off feature flag while leaving existing sessions on legacy behavior.
6. Limit the first implementation phase to a graph skeleton, pure routing, and legacy-parity verification.
7. Confine any dependency set admitted by the compatibility and security gates to the OA image and the non-persistent routing use case.

## 3. Non-Goals

This design does not:

- merge or remove any of the six Agent microservices;
- create a seventh workflow, gateway, or checkpointer service;
- migrate the frontend, public backend API, main-backend data model, or non-OA Agent implementations to LangGraph;
- move OA business state into LangGraph state;
- add PostgreSQL, SQLite, Redis, or file-based LangGraph checkpoint persistence;
- change the configured storage backend used by the existing OA MAS memory store;
- add RAG, vector retrieval, tool calling, model-directed routing, or autonomous planning;
- redesign Agent prompts or clinical/behavioural logic;
- claim clinical effectiveness, user acceptance, or improved goal adherence;
- remove the legacy path during this rollout.

## 4. Version and Security Boundary

### 4.1 Runtime compatibility gate

OA does not currently have the main backend's fixed dependency stack. Its `mas/OA/requirements.txt` leaves `fastapi` and `uvicorn` unpinned and contains no explicit `pydantic` or `httpx` requirement. Consequently, this design does not preselect or claim compatibility for a LangGraph, LangChain Core, FastAPI, Uvicorn, Pydantic, or HTTPX version set.

Before implementation, an isolated clean Python 3.10 environment must resolve candidate exact pins and run an OA-specific runtime probe covering imports, FastAPI startup, request validation, graph compilation, and one in-memory invocation. The accepted versions must then be pinned only in the OA image. The probe must also demonstrate that no main-backend requirements, environment, lock file, or installed package changes. If no security-acceptable and runnable combination is found, implementation stops and graph rollout remains disabled.

`langgraph-checkpoint-postgres`, Psycopg 3, and every persistent saver implementation remain excluded. The main backend and MMA, SOA, GRA, SCA, and SSA images must not gain LangGraph dependencies.

### 4.2 Known vulnerability

The historical Pydantic 1-compatible candidate `langgraph==0.2.28` is within the affected range of [GHSA-g48c-2wqr-h844](https://github.com/advisories/GHSA-g48c-2wqr-h844), which covers LangGraph versions through 1.0.9 and identifies 1.0.10 as patched. The advisory concerns unsafe object reconstruction while loading attacker-modified, msgpack-encoded persistent checkpoints. The runtime compatibility gate may select this candidate only under the documented exception; it may instead reject it and stop implementation.

This design does not describe an exception candidate as patched or generally secure. Its restricted use can proceed only when the runtime compatibility gate passes and the vulnerable checkpoint-loading path remains unused. The following controls are mandatory:

- compile and invoke the graph without a checkpointer;
- do not import or instantiate checkpoint savers or checkpoint serializers;
- do not serialize, persist, load, or resume LangGraph checkpoints;
- do not accept graph state bytes or serialized graph objects from an HTTP request or the OA memory store;
- construct every graph input from validated OA business-state fields;
- confine the dependency to the OA image;
- assert in CI and at OA runtime startup that the compiled graph's checkpointer is `None`;
- retain dependency-scanner visibility and document the exception as limited to `graph_v1` in-memory routing.

The exception owner is the project maintainer. It must be reviewed and either renewed or closed before Phase 2 begins or on 30 September 2026, whichever occurs first. The controls reduce exposure to the checkpoint-deserialization path only; they are not a general security certification of LangGraph, OA, or the MAS. The exception ends immediately if any persistent checkpointer, custom msgpack hook, untrusted serialized state, or cross-service graph-state transport is proposed. Such a change requires a separate design and a non-vulnerable dependency strategy.

## 5. Component Architecture

| Component | Responsibility | Explicitly does not own |
|---|---|---|
| Frontend | Sends and renders the existing MAS chat contract | Workflow mode, graph state, route selection |
| Main backend | Preserves the public chat/session API, stores its existing message mirror, and forwards the MAS turn through the existing gateway seam | LangGraph dependency, graph execution, next-Agent decisions |
| OA ingress adapter | Validates the turn envelope, loads the OA session record, chooses legacy or `graph_v1`, and returns a route result | Conversation-message writes, prompt logic, Agent generation |
| OA business-state repository | Reads and writes workflow metadata and existing OA documents through `mas_memory_store`; existing Agent callbacks remain the only conversation-message writers | LangGraph checkpoints |
| OA legacy adapter | Executes the current deterministic routing behavior for sessions assigned `legacy` | Graph-mode state changes |
| OA graph adapter | Constructs ephemeral graph state, invokes the compiled in-memory graph, and returns one route decision | Business-state persistence and external HTTP effects |
| OA effect executor | Calls the selected Agent endpoint and applies existing timeout rules | Conversation-message writes or selecting an alternative Agent after transport failure |
| MMA, SOA, GRA, SCA, SSA | Preserve their current HTTP contracts and specialised Agent behavior | Final routing authority |

The main backend may require a compatibility-only forwarding adjustment at its existing MAS gateway seam so OA receives the user-turn envelope. This does not move graph code or workflow state into the main backend. Public frontend/backend contracts and backend database ownership remain unchanged.

## 6. Single Orchestration Ownership

OA is the only component allowed to decide which Agent handles a graph-mode event. LangGraph is an internal decision engine used by OA; it is not a peer orchestrator.

The ownership rules are:

1. The main backend submits a turn to OA and does not preselect SOA, GRA, or SCA for `graph_v1`.
2. The graph returns a typed `RouteDecision`; it does not issue HTTP requests or write business state.
3. OA validates the decision and performs the external Agent call. SOA, GRA, and SCA continue to write user and assistant conversation messages exclusively through OA `/receive_user_message` and `/receive_message` callbacks.
4. An Agent's call to OA `/trigger_agent` is treated as a transition intent. In `graph_v1`, OA validates that intent against the graph before executing it. The Agent-supplied name is not authoritative.
5. The legacy adapter remains authoritative for `legacy` sessions and reproduces current behavior without invoking LangGraph.
6. Network or model failure never authorises OA to try an arbitrary next Agent. The only compatibility transition is the existing SOA result whose semantic reason states that the message should be sent to GRA.

These rules prevent the main backend, an Agent, OA procedural code, and LangGraph from making competing route decisions.

### 6.1 Root request lifecycle

Before graph-mode dispatch, OA acquires the patient/session-generation lock and permits only one active root request reservation for that generation. The reservation lifecycle is:

1. Reload the current generation and derive the root request identity from the accepted request identity and bounded request fingerprint.
2. If the same root identity is active, return its known status without dispatch. If a different root request conflicts with the active reservation, return a concurrency conflict without dispatch.
3. Persist the active root reservation, including generation and route status, before releasing the lock.
4. Keep the reservation active but release the lock throughout the outbound Agent HTTP call. No patient lock crosses network I/O.
5. Permit `/trigger_agent` only when its transition identity links to this active root reservation and generation.
6. After the Agent result and every nested transition are reconciled, reacquire the lock and clear the active reservation while archiving its terminal status. A stale result cannot clear or update a newer generation.

This lifecycle provides one active root request and at-most-one root dispatch per patient generation without deadlocking nested OA callbacks.

### 6.2 `/trigger_agent` re-entrancy and transition identity

Agent processing can call OA `/trigger_agent` while OA is still awaiting the original outbound Agent request. OA therefore must never hold a patient-scoped lock across an outbound HTTP call.

For `graph_v1`, every `/trigger_agent` callback follows this sequence:

1. Acquire the patient lock, reload the latest `workflow_mode`, `session_generation`, turn, and active root request reservation, and reject stale-generation or unassociated callbacks.
2. Derive a deterministic transition identity from the active root request identity, session generation, current turn, and requested next Agent. Validate both the transition intent and its association with the root reservation.
3. If the identity is already reserved or completed, return the recorded duplicate result without another dispatch. If it conflicts with current state, return a transition conflict without dispatch.
4. Persist an at-most-once reservation for the transition identity, then release the lock before calling the downstream Agent.
5. After the call, reacquire the lock, reload the generation, and record the outcome only if the reservation still belongs to that generation.

This reservation makes one transition dispatch at most once. A process failure after reservation but before outcome recording leaves the transition unresolved and requires reconciliation; it is never automatically redispatched as a different or duplicate transition.

## 7. Session Mode and Feature Flag

The rollout flag is `OA_LANGGRAPH_NEW_SESSIONS_ENABLED` and defaults to `false`.

OA stores the following mode fields in the patient session record:

```json
{
  "workflow_mode": "legacy | graph_v1",
  "workflow_version": "legacy_v1 | oa_graph_v1",
  "session_generation": 1
}
```

The assignment rules are deterministic:

- A pre-existing active record without `workflow_mode` is `legacy`.
- Enabling the flag does not migrate or reinterpret an existing session.
- When OA creates or explicitly resets a session boundary, it increments `session_generation` and assigns `graph_v1` only if the flag is enabled at that moment; otherwise it assigns `legacy`.
- Scheduled review startup follows the same new-session assignment rule after OA resets the completed session state.
- Once assigned, the mode remains fixed until completion or the next explicit session reset.
- Disabling the flag stops assigning `graph_v1` to future sessions. It does not silently switch an active graph session mid-conversation.

If the LangGraph dependency cannot be imported or the graph cannot be compiled at OA startup, OA reports graph routing unavailable, assigns new sessions to `legacy`, and remains healthy for legacy traffic.

## 8. State Model

### 8.1 OA-persisted business state

The OA memory store remains authoritative. The graph must not hold the only copy of any field needed after restart. The relevant persisted record contains:

- `patient_id`;
- `session_generation`;
- `workflow_mode` and `workflow_version`;
- `turn_index`;
- `chat_history`;
- derived `session_status` (`active` below turn 15, otherwise `completed`);
- `last_agent` and the last completed route outcome;
- the active root request reservation, archived root outcomes, and a bounded transition-reservation ledger used to suppress duplicate dispatch;
- a degradation marker when graph routing fell back to the parity router.

The existing `review_schedule` and session-note documents retain their present responsibilities. They are not copied into graph checkpoints.

### 8.2 Ephemeral graph state

A new graph-state dictionary is created for each invocation and discarded afterward. It contains only validated JSON-compatible values:

- `patient_id`, `session_generation`, and `workflow_version`;
- `request_id` generated or accepted by OA;
- `event_type` (`user_turn`, `agent_transition_intent`, or `scheduled_start`);
- a bounded `turn_index` and `session_status`;
- the minimum history facts needed for deterministic routing, not the full persisted record unless required for parity;
- `requested_agent` for a transition intent;
- `selected_agent`, `route_reason`, and `route_status`;
- a structured error category when routing cannot complete.

No HTTP client, database session, Pydantic model instance, callable, Agent response object, secret, or binary payload may enter graph state.

## 9. Graph Skeleton and Routing Rules

The graph uses a composite oracle. `classify_session` first applies the completion guard: turn 15 or an explicit completed status terminates without selecting an Agent. Only an active turn reaches the selector characterised by `app/services/mas/legacy_routing.py` and `ChatService`: 0 through 5 select SOA, 6 through 13 select GRA, and 14 selects SCA. The older `mas_routes.py` and OA status display classify turn 6 as SOA. That discrepancy remains documented legacy behavior and is not repaired or imported into the graph.

The phase-one graph contains pure nodes only:

1. `validate_event` checks required identifiers, event type, integer turn range, and JSON-safe state.
2. `classify_session` confirms that the invocation is `graph_v1` and that the session is active.
3. `select_legacy_parity_route` applies the characterised legacy routing table.
4. `validate_transition_intent` accepts only the transition that the current state permits.
5. `emit_route_decision` returns a typed decision for OA's effect executor.
6. `emit_completed` returns a terminal decision without selecting an Agent.
7. `emit_route_error` returns a typed, non-secret error without an Agent call.

Conditional edges are deterministic:

```text
START
  -> validate_event
      -> invalid --------------------------> emit_route_error -> END
      -> valid ----------------------------> classify_session

classify_session
  -> turn_index 15 or completed -----------> emit_completed -> END
  -> active user_turn ----------------------> select_legacy_parity_route
  -> active agent_transition_intent --------> validate_transition_intent
  -> active scheduled_start ----------------> select_legacy_parity_route

select_legacy_parity_route
  -> turn_index 0..5 ----------------------> emit_route_decision(SOA) -> END
  -> turn_index 6..13 ---------------------> emit_route_decision(GRA) -> END
  -> turn_index 14 -------------------------> emit_route_decision(SCA) -> END
```

The selector accepts active turns 0 through 14 only. It has no completed or `>=15` branch, so completion and Agent selection cannot overlap.

The existing SOA-to-GRA compatibility signal is represented as a validated transition event, not a catch-all fallback. SSA close-out and MMA scheduled extraction remain OA-owned procedural workflows in phase one; they are not folded into the user-turn graph skeleton. Agent transition intents involving SSA are checked against the same legacy parity contract before OA executes them.

## 10. Request Data Flows

For a legacy session, OA loads the record, invokes the legacy adapter, and returns the existing response contract. Existing Agent callbacks continue to write conversation messages through OA. LangGraph is not invoked.

For `graph_v1`, OA ingress reserves one active root request under the patient/generation lock, constructs fresh graph state, obtains one `RouteDecision`, and releases the lock before calling exactly one Agent. The reservation remains active during HTTP and is cleared or archived under lock only after the Agent result and nested transitions reconcile. OA may persist workflow metadata and reservations, but it does not write the user or assistant conversation message. As today, SOA, GRA, and SCA write the user message through OA `/receive_user_message` and the assistant message through OA `/receive_message`; those callbacks remain the only conversation-write path in Phases 1 and 2. The graph terminates within the request and stores no execution frame.

OA and the main backend must not mirror the same message into `goal_reviews` through an additional graph-ingress path. Any future change to the Agent callback contract or conversation-write ownership requires a separate design.

An Agent call to `/trigger_agent` is converted to a transition intent associated with the active root reservation. Legacy sessions retain current behavior; graph sessions execute only a graph-approved, generation-matching intent. Missing association, mismatch, duplicate, or conflict returns known status or a contract error without another downstream call.

Review scheduling, scheduled SOA starts, daily reset, and MMA extraction remain procedural OA workflows. A scheduled start creates a new session generation and applies the same feature-flag assignment.

## 11. Recovery and Degradation

After restart, OA recompiles the graph and reconstructs the next invocation from persisted `workflow_mode`, `session_generation`, `turn_index`, history facts, and last route. It never performs a LangGraph resume.

If graph execution fails before dispatch, OA uses the tested parity router for that request, records degradation, and leaves the session latched as `graph_v1`. Insufficient or invalid OA state fails closed. After dispatch, a timeout never causes a different Agent call; the same request or transition identity is governed by its at-most-once reservation. Callback persistence failure returns an error rather than false success.

## 12. Error Handling Contract

- Validation, unsupported-version, transition-conflict, and unusable-state errors produce no Agent call.
- Graph import failure keeps OA healthy and assigns new sessions to legacy.
- Graph invocation failure permits only the parity degradation described above.
- Agent timeout, HTTP failure, and invalid JSON return typed Agent errors without arbitrary fallback.
- Only the semantic SOA `should be sent to GRA` result permits the compatibility transition.
- Duplicate requests or transitions return the known reservation/result; callback persistence failures never report completion.

Logs include request/session identifiers, mode, category, and selected Agent, but exclude secrets, prompts, and connection strings.

## 13. Testing Strategy

- Selector parity tests cover active turns 0, 5, 6, 13, and 14 against `app/services/mas/legacy_routing.py`. A separate completion-guard test proves turn 15 selects no Agent. Tests also prove the SOA-to-GRA edge is semantic rather than transport-driven and record without repairing the turn-6 difference in `mas_routes.py` and OA status output.
- Topology tests prove every path terminates and graph nodes perform no HTTP or storage I/O.
- Mode tests cover missing fields, flag on/off, reset assignment, latching, and unavailable LangGraph runtime.
- OA contract tests prove `/receive_user_message` and `/receive_message` remain the sole conversation writers, graph ingress performs no duplicate write, and existing Agent payloads/backend responses remain unchanged.
- Root-lifecycle tests prove one active reservation per patient generation, duplicate status reuse, conflict rejection, one root dispatch, lock release during HTTP, reservation retention during HTTP, and lock-protected archive/clear only after Agent and nested-transition reconciliation.
- Re-entrancy tests simulate `/trigger_agent` during an outstanding root call and prove root-reservation association, generation reloading, identity validation, no lock across HTTP, one dispatch per transition, and no dispatch for duplicate or conflicting callbacks.
- Restart tests discard all ephemeral state, rebuild from OA records, and verify parity degradation and fail-closed corrupt-state behavior.
- Compatibility tests run in clean Python 3.10 before pin selection and prove OA imports, FastAPI startup, validation, graph compilation, and one in-memory invocation without changing the main backend.
- Security/deployment tests enforce OA-only exact pins after that probe, six unchanged services, compiled checkpointer `None` in CI and runtime, no saver/Psycopg 3/msgpack path, and a passing legacy suite with the flag off.

## 14. Phased Scope

### Phase 1: graph skeleton and legacy parity

Phase 1 creates only:

- OA-local graph-state and route-decision contracts compatible with the exact OA stack selected by the clean Python 3.10 probe;
- the compiled in-memory graph skeleton;
- pure validation, classification, routing, and terminal nodes;
- the canonical legacy parity adapter;
- unit, topology, security-boundary, and golden parity tests.

Phase 1 does not connect the graph to live Agent HTTP calls, enable rollout traffic, add persistent checkpoints, implement RAG, add tool calling, change prompts, move schedules into the graph, or remove any legacy code.

#### Phase 1 acceptance

Phase 1 is accepted independently when:

1. A clean Python 3.10 probe has produced a security-acceptable, runnable, OA-only exact dependency set; otherwise implementation has stopped without changing the main backend.
2. The graph skeleton compiles with its checkpointer asserted as `None` in tests and at runtime startup.
3. Every node is pure, every path terminates, and no live Agent, database, or message callback is invoked.
4. Selector golden tests match `legacy_routing.py` and `ChatService` at active turns 0..5 SOA, 6..13 GRA, and 14 SCA; a separate completion test proves turn 15 emits no Agent decision.
5. Tests document the legacy turn-6 discrepancy without changing `mas_routes.py` or OA status behavior.
6. Existing Agent callback contracts remain the sole conversation-write path and the complete legacy regression suite passes.
7. No RAG, tool calling, persistent checkpoint, feature-flag traffic, live effect executor, or Phase 2/3 integration is present.

### Phase 2: OA integration behind the feature flag

Phase 2 adds the OA ingress adapter, session-mode latching, the single active root request reservation lifecycle, effect executor integration, nested transition identity/reservation handling, stable response mapping, and default-off `OA_LANGGRAPH_NEW_SESSIONS_ENABLED`. It preserves the legacy path and keeps existing Agent callbacks as the sole conversation writers.

### Phase 3: controlled rollout and resilience verification

Phase 3 enables graph assignment in a controlled environment, verifies restart reconstruction, exercises fault injection, confirms legacy rollback for new sessions, and records route-parity and degradation observations. It does not expand the graph's functional responsibilities.

Any future RAG, tool-calling, persistent checkpoint, dependency-modernisation, or service-consolidation work requires a separate approved design.

## 15. Later-Phase Guardrails

Phase 2 and Phase 3 may proceed only after Phase 1 passes its independent acceptance list and the project maintainer reviews the GHSA exception before the stated expiry. Later phases must retain OA-only orchestration, callback-only conversation writes, session-latched rollout, restart reconstruction from OA business state, one active root reservation per patient generation, at-most-once root and transition dispatch, and the unchanged six-service topology.
