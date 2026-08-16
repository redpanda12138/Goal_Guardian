"""Main-backend adapter for the provider-neutral retrieval boundary."""

from typing import Any, Iterable, List, Mapping

from app.models.mas_workflow_models import RetrievalResult
from mas.common.lexical_retriever import LexicalRetriever


def retrieve_context(
    query: str,
    documents: Iterable[Mapping[str, Any]],
    *,
    top_k: int = 3,
    max_content_chars: int = 1200,
) -> List[RetrievalResult]:
    """Return only validated, versioned results from approved local documents."""

    retriever = LexicalRetriever(documents, max_content_chars=max_content_chars)
    return [RetrievalResult(**result) for result in retriever.search(query, top_k=top_k)]


def validate_retrieval_trace(results: Any) -> List[dict]:
    """Revalidate a retrieval trace received from another MAS service."""

    if not isinstance(results, list) or len(results) > 5:
        raise ValueError("retrieval_results must be a list of at most five items")

    validated = []
    for raw in results:
        if not isinstance(raw, Mapping):
            raise ValueError("each retrieval result must be an object")
        result = RetrievalResult(**dict(raw))
        if not result.content or len(result.content) > 1200:
            raise ValueError("retrieved content must contain at most 1200 characters")
        if not 0 < result.score <= 1:
            raise ValueError("retrieval score must be between zero and one")
        if result.metadata.get("context_role") != "untrusted_data":
            raise ValueError("retrieved context must be marked as untrusted data")
        validated.append(result.dict())
    return validated
