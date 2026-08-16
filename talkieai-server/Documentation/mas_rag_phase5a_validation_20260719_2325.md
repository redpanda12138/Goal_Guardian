# MAS RAG Phase 5A Validation

## Scope

This phase established a provider-neutral retrieval boundary for explicitly
approved local documents. It did not add a medical knowledge corpus, call an
external embedding or search service, or inject retrieved text into model
generation.

## Implemented Boundary

1. `LexicalRetriever` accepts only explicitly approved documents with unique,
   contract-compatible source identifiers, non-empty content, and
   JSON-compatible metadata.
2. Queries are normalised and bounded to 1,000 characters. Result count is
   bounded to five and retrieved content is bounded to a configurable maximum.
3. Ranking uses deterministic token overlap. A query with no lexical match
   returns no context instead of inventing a source.
4. Retrieval identifiers are stable for the same normalised query and source.
5. Returned metadata preserves source metadata and adds `context_role` as
   `untrusted_data`, plus content truncation and original-length audit fields.
6. The main-backend adapter converts raw results to the existing versioned
   `RetrievalResult` contract.

The lexical implementation is intentionally replaceable. It provides a small,
offline validation seam and does not imply that lexical ranking is sufficient
for a deployed health information system.

## Verification

- RAG retrieval boundary: 11 passed.
- RAG and workflow contract tests: 36 passed.
- Main backend top-level suite: 133 passed, 1 skipped, and 1 existing expected
  failure.
- OA/LangGraph suite: 57 passed.
- `git diff --check` reported no whitespace errors before commit.

The main backend suite required `PYTHONUTF8=1` because existing import tests
spawn Python processes that otherwise decode a UTF-8 JSON file with the Windows
GBK locale. The unrestricted repository-level pytest collector also encounters
an inaccessible legacy virtual-environment file, so validation used the
project's established main-backend and OA test scopes.

## Remaining Boundary

No approved production corpus has been supplied. Retrieval is not yet connected
to the GRA decision flow, and retrieved context is not yet included in provider
prompts. Phase 5B should add an opt-in corpus configuration, connect retrieval
to the graph path, preserve source traceability in responses, and test prompt
injection resistance before any live-provider validation.
