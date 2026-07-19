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
