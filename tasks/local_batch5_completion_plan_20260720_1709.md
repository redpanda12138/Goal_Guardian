# Local Batch 5 Completion Plan

## Overview

Complete every Agent Workflow Rewrite task that can be implemented and
verified without a remote deployment. The work will preserve the disabled-by-
default rollout boundary and will not enable production traffic, call a live
model provider, or modify production data.

## Architecture Decisions

- Keep LangGraph inside the independently packaged OA service. The main backend
  consumes only versioned HTTP/JSON projections.
- Treat the OA business record as the durable workflow state. Add an explicit,
  deterministic stage projection rather than introducing an incompatible
  checkpointer into the main backend.
- Shadow comparison remains side-effect-free: it may compute and return route
  parity but cannot reserve requests, persist messages, dispatch Agents, or
  execute tools.
- Rollout remains opt-in and can be restricted to test patients/accounts. Empty
  allowlists retain the existing global-flag semantics for backward
  compatibility.
- Main-backend and OA tests run in separate Python processes and dependency
  environments to avoid the two `app` modules and incompatible Pydantic stacks
  sharing one interpreter.

## Task List

### Phase 1: Explicit workflow stage projection

- [ ] Add failing OA tests for opening, review, waiting, closing, summary, and
  completed stage projection.
- [ ] Implement the pure stage projector and expose it in workflow/session
  responses without changing legacy response behavior.
- [ ] Add failing main-backend tests and project graph stages into Dashboard
  session state only when workflow mode is `graph_v1`.

### Checkpoint 1

- [ ] OA focused tests pass in the OA environment.
- [ ] Dashboard and gateway regression tests pass in the main environment.

### Phase 2: Shadow comparison and test-only rollout

- [ ] Add failing tests proving shadow decisions match legacy boundaries and
  cause no reservations, persistence, or Agent dispatch.
- [ ] Implement a pure OA shadow endpoint plus a main-backend opt-in seam.
- [ ] Add test-patient and test-account allowlists with disabled-by-default,
  rollback-safe behavior.

### Checkpoint 2

- [ ] Shadow and rollout tests pass.
- [ ] Existing graph sessions remain latched when allocation is disabled.
- [ ] Non-allowlisted identities continue through the legacy path.

### Phase 3: Local validation orchestration

- [ ] Add a local validation runner that launches main-backend and OA suites in
  separate interpreters and reports missing environments clearly.
- [ ] Validate Docker Compose configuration and all offline/local test scopes.
- [ ] Run the frontend unit suite and H5 production build.
- [ ] Perform browser checks if an executable local browser harness is
  available; otherwise retain an explicit evidence boundary.

### Checkpoint 3

- [ ] All executable local checks pass.
- [ ] No network-dependent or server-only result is claimed.
- [ ] Validation evidence records commands, results, warnings, and exclusions.

### Phase 4: Documentation and delivery

- [ ] Update local configuration examples and rollout/rollback instructions.
- [ ] Update the authoritative rewrite checklist to reflect completed work and
  identify only server/staging tasks as remaining.
- [ ] Run final diff, secret, build, and regression checks.
- [ ] Commit each verified increment and leave the worktree clean.

## Risks and Mitigations

| Risk | Impact | Mitigation |
|---|---|---|
| Main and OA dependency stacks conflict | Full test collection fails | Separate interpreters and commands |
| Shadow mode accidentally writes state | Duplicate messages or actions | Pure endpoint tests with persistence/dispatch spies |
| Stage projection contradicts legacy turns | Dashboard inconsistency | Central pure projector with boundary tests |
| Allowlist changes active graph sessions | Broken continuity | Apply allowlists only when allocating/entering new graph sessions |
| Local environment lacks Docker/browser/runtime | Incomplete evidence | Run all available checks and record exact non-code blocker |

## Remote-only Exclusions

- Test-account rollout against deployed services.
- Real traffic Shadow Mode observation.
- Deployment rollback drill.
- Live model-provider and production-corpus validation.
- Domain-expert corpus and safety review.

