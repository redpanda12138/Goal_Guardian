# MAS Batch 5 Local Validation

## Scope

This record covers the Agent Workflow Rewrite tasks that could be implemented
and verified without a remote deployment. It documents prototype-level
technical validation only. No production traffic, deployed test account,
external model provider, or production RAG corpus was used.

## Implemented locally

1. OA now projects explicit `opening`, `review_decision`, `waiting_user`,
   `closing`, and `summary` workflow stages from its durable business record.
2. A turn-15 SCA transition can enter SSA summary while a new user turn at the
   same boundary remains completed and cannot restart the workflow.
3. The main Dashboard validates graph stage/version/generation fields and marks
   their source as workflow state. Legacy session payloads remain unchanged.
4. OA exposes a pure Shadow decision endpoint. Tests prove that it does not
   load or save OA records, reserve requests, dispatch Agents, or execute tools.
5. New graph allocation can be restricted by patient ID in OA, and main-backend
   graph entry can be restricted by account ID. Both remain disabled by
   default, and disabling allocation does not rewrite active graph generations.
6. Main-backend and OA test suites are orchestrated in separate Python
   processes to prevent dependency and `app` module collisions.

## Automated verification

The local runner completed with `LOCAL_VALIDATION=PASS`:

- Main backend: 165 passed, 1 skipped, 1 existing expected failure.
- OA/LangGraph: 71 passed.
- Frontend confirmation state: 9 passed.
- Docker Compose configuration: valid.
- H5 production build: succeeded.

Observed warnings were existing Starlette/httpx test-client, FastAPI startup
event, SQLAlchemy declarative-base, Sass import/API, Browserslist data, and
vue-router import deprecations. No new assertion or build error was present.

The repository-wide `npm run type-check` was also inspected but is not included
in the passing Batch 5 gate. It exits with TS6504 before analysing this change
because generated `src/**/*.vue.js` files are supplied as root files while
`allowJs` is disabled. The failure is pre-existing frontend type-check debt;
this Batch did not add or modify those generated files.

## Browser observation

An isolated agent-browser session loaded the built H5 application from a
temporary server bound only to `127.0.0.1`. The page title was `Talkie`, and the
interactive snapshot exposed two text boxes and the Login control. The login
screen rendered without horizontal overflow or control overlap at 320x800 and
1440x900. The browser console contained no error and one existing vue-router
deprecation warning.

Evidence:

- `talkieai-uniapp/Documentation/h5_local_browser_320x800_20260720_1736.png`
- `talkieai-uniapp/Documentation/h5_local_browser_1440x900_20260720_1736.png`

The authenticated confirmation card was not exercised because no test account
or local authenticated backend session was supplied. Its deterministic state
machine and H5 compilation were verified, but deployed authenticated browser
interaction remains a staging task.

## Remaining server/staging boundary

- Observe Shadow comparisons against deployed legacy traffic.
- Allocate graph sessions only to aligned test account/patient identities.
- Exercise authenticated write confirmation, refresh recovery, and dashboard
  projection against deployed services.
- Perform a controlled rollback drill.
- Validate live model-provider behavior and any approved production corpus.

These remaining checks are operational deployment validation. They do not
change the conclusion that the locally scoped Batch 5 implementation and
offline verification tasks completed successfully. The independent frontend
type-check debt recorded above remains outside that conclusion.
