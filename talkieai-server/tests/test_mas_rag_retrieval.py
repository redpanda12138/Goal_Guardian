import importlib
from pathlib import Path

import pytest


SERVER_ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def retrieval(monkeypatch):
    monkeypatch.syspath_prepend(str(SERVER_ROOT))
    common = importlib.import_module("mas.common.lexical_retriever")
    service = importlib.import_module("app.services.mas.rag_retrieval")
    return common, service


def approved_documents():
    return [
        {
            "source_id": "source-walking-01",
            "content": "A weekly walking review can compare completed sessions with the planned frequency.",
            "approved": True,
            "metadata": {"title": "Walking review guide", "source": "curated-local"},
        },
        {
            "source_id": "source-sleep-001",
            "content": "A sleep routine review can examine consistency of bedtime and wake time.",
            "approved": True,
            "metadata": {"title": "Sleep review guide", "source": "curated-local"},
        },
    ]


def test_retrieval_ranks_matching_approved_sources_and_returns_stable_ids(retrieval):
    common, _service = retrieval
    retriever = common.LexicalRetriever(approved_documents(), max_content_chars=1200)

    first = retriever.search("weekly walking progress", top_k=2)
    second = retriever.search("weekly walking progress", top_k=2)

    assert first == second
    assert first[0]["source_id"] == "source-walking-01"
    assert first[0]["retrieval_id"].startswith("retrieval-")
    assert 0 < first[0]["score"] <= 1
    assert first[0]["metadata"]["context_role"] == "untrusted_data"
    assert first[0]["metadata"]["title"] == "Walking review guide"


def test_no_lexical_match_returns_no_context_instead_of_fabricating_a_source(retrieval):
    common, _service = retrieval
    retriever = common.LexicalRetriever(approved_documents())

    assert retriever.search("quantum compiler", top_k=2) == []


@pytest.mark.parametrize(
    "documents",
    [
        [{"source_id": "source-one", "content": "text", "approved": False, "metadata": {}}],
        [
            {"source_id": "duplicate-source", "content": "one", "approved": True, "metadata": {}},
            {"source_id": "duplicate-source", "content": "two", "approved": True, "metadata": {}},
        ],
        [{"source_id": "short", "content": "text", "approved": True, "metadata": {}}],
        [{"source_id": "source-valid", "content": "", "approved": True, "metadata": {}}],
    ],
)
def test_corpus_rejects_unapproved_duplicate_or_malformed_documents(retrieval, documents):
    common, _service = retrieval

    with pytest.raises(common.CorpusValidationError):
        common.LexicalRetriever(documents)


def test_retrieved_content_is_bounded_and_records_original_length(retrieval):
    common, _service = retrieval
    content = "walking " * 400
    retriever = common.LexicalRetriever(
        [
            {
                "source_id": "source-long-0001",
                "content": content,
                "approved": True,
                "metadata": {"title": "Long source"},
            }
        ],
        max_content_chars=80,
    )

    result = retriever.search("walking", top_k=1)[0]

    assert len(result["content"]) == 80
    assert result["metadata"]["truncated"] is True
    assert result["metadata"]["original_length"] == len(content)


def test_main_backend_adapter_returns_versioned_retrieval_contracts(retrieval):
    _common, service = retrieval

    results = service.retrieve_context(
        "sleep routine",
        approved_documents(),
        top_k=1,
    )

    assert len(results) == 1
    assert results[0].contract_version == "v1"
    assert results[0].source_id == "source-sleep-001"
    assert results[0].metadata["context_role"] == "untrusted_data"


@pytest.mark.parametrize("query", ["", "   ", "x" * 1001])
def test_query_boundary_rejects_empty_or_oversized_input(retrieval, query):
    common, _service = retrieval
    retriever = common.LexicalRetriever(approved_documents())

    with pytest.raises(ValueError):
        retriever.search(query)
