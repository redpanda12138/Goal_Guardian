# Adaptive review and grounded RAG release

## Added

- OA-owned, persisted stage decisions based on conversation evidence and pacing ranges.
- Explicit pause, resume, extension and end-session controls in the chat client.
- Generation-bound tool confirmation and replay handling for longer reviews.

## Fixed

- General knowledge exchanges no longer advance the personal goal-review stage.
- Knowledge answers are checked against retrieved passages and server-rendered source references.
- Mixed knowledge/review turns retain personal evidence without treating papers as user progress.
- Completed conversations remain read-only; pending writes require explicit confirmation.

## Verification before upload

On 31 August 2026, the OA suite passed 146 tests. The application suite passed
185 tests, with one skip and one expected failure. The three directly relevant
frontend suites passed 17 tests. Dependency deprecation warnings remain.
These counts overlap earlier validation runs and must not be added to them.

## Deployment and activation

Deploy the immutable Git commit, preserving the existing production environment,
database, uploaded files, speech model and production RAG corpus. The offline
research test corpus is not part of this code release.

`OA_ADAPTIVE_ENABLED` controls allocation to new adaptive sessions. Enable the
backend's `MAS_OA_GRAPH_SEAM_ENABLED` at the same time and ensure its account
allowlist includes every account allocated an adaptive session. Existing sessions
retain their recorded workflow mode. Do not reset existing sessions during deployment.

Keep adaptive allocation disabled until the compatible chat client is available
and the authenticated canary flow has passed. Older installed mobile clients do
not have the new pause/extension controls. Uploading frontend source does not
update an installed mobile application.

## Rollback

Before replacing containers, retain the current image IDs under rollback tags,
archive the active release directory and record the current Compose configuration.
Keep the existing backend-files volume and model bind mount. Build replacement
images before switching services. Reuse the existing Compose project name so
data volumes and the reverse proxy target remain unchanged.

If health or authenticated smoke checks fail, stop the new services and restore
the saved images and Compose configuration. Preserve all new database records;
this release does not require a destructive database migration. Disabling new
adaptive allocation alone does not change already-latched adaptive sessions.

Production deployment status is recorded separately after verification.
