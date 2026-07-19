"""Small, deterministic retrieval boundary for explicitly approved local sources."""

from __future__ import annotations

import hashlib
import json
import math
import re
from copy import deepcopy
from typing import Any, Dict, Iterable, List, Mapping, Sequence, Tuple


_IDENTIFIER_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{7,127}$")
_TOKEN_PATTERN = re.compile(r"[a-z0-9]+|[\u4e00-\u9fff]", re.IGNORECASE)
_MAX_QUERY_CHARS = 1000


class CorpusValidationError(ValueError):
    """Raised when a source cannot cross the approved-corpus boundary."""


class LexicalRetriever:
    """Retrieve bounded excerpts using deterministic token overlap.

    This implementation deliberately has no model or network dependency. It is a
    replaceable retrieval seam, not a claim that lexical matching is the final
    production ranking strategy.
    """

    def __init__(
        self,
        documents: Iterable[Mapping[str, Any]],
        *,
        max_content_chars: int = 1200,
    ) -> None:
        if isinstance(max_content_chars, bool) or not isinstance(max_content_chars, int):
            raise ValueError("max_content_chars must be an integer")
        if not 32 <= max_content_chars <= 8000:
            raise ValueError("max_content_chars must be between 32 and 8000")

        self._max_content_chars = max_content_chars
        self._documents = self._validate_documents(documents)

    @staticmethod
    def _validate_documents(
        documents: Iterable[Mapping[str, Any]],
    ) -> Tuple[Dict[str, Any], ...]:
        if isinstance(documents, (str, bytes, Mapping)):
            raise CorpusValidationError("documents must be an iterable of objects")

        validated: List[Dict[str, Any]] = []
        seen_source_ids = set()
        try:
            candidates = list(documents)
        except TypeError as exc:
            raise CorpusValidationError("documents must be iterable") from exc

        for index, document in enumerate(candidates):
            if not isinstance(document, Mapping):
                raise CorpusValidationError(f"document {index} must be an object")

            source_id = document.get("source_id")
            if not isinstance(source_id, str) or not _IDENTIFIER_PATTERN.fullmatch(source_id):
                raise CorpusValidationError(f"document {index} has an invalid source_id")
            if source_id in seen_source_ids:
                raise CorpusValidationError(f"duplicate source_id: {source_id}")
            seen_source_ids.add(source_id)

            if document.get("approved") is not True:
                raise CorpusValidationError(f"source {source_id} is not explicitly approved")

            content = document.get("content")
            if not isinstance(content, str) or not content.strip():
                raise CorpusValidationError(f"source {source_id} has empty content")

            metadata = document.get("metadata", {})
            if not isinstance(metadata, Mapping):
                raise CorpusValidationError(f"source {source_id} metadata must be an object")
            metadata_copy = deepcopy(dict(metadata))
            try:
                json.dumps(metadata_copy, allow_nan=False)
            except (TypeError, ValueError) as exc:
                raise CorpusValidationError(
                    f"source {source_id} metadata must be JSON-compatible"
                ) from exc

            validated.append(
                {
                    "source_id": source_id,
                    "content": content,
                    "metadata": metadata_copy,
                    "tokens": frozenset(_tokenize(content)),
                }
            )

        return tuple(validated)

    def search(self, query: str, *, top_k: int = 3) -> List[Dict[str, Any]]:
        normalized_query = _validate_query(query)
        if isinstance(top_k, bool) or not isinstance(top_k, int) or not 1 <= top_k <= 5:
            raise ValueError("top_k must be an integer between 1 and 5")

        query_tokens = frozenset(_tokenize(normalized_query))
        if not query_tokens:
            return []

        ranked: List[Tuple[float, str, Dict[str, Any]]] = []
        for document in self._documents:
            overlap = query_tokens.intersection(document["tokens"])
            if not overlap:
                continue
            score = len(overlap) / len(query_tokens)
            if not math.isfinite(score) or score <= 0:
                continue
            ranked.append((score, document["source_id"], document))

        ranked.sort(key=lambda item: (-item[0], item[1]))
        return [
            self._to_result(normalized_query, score, document)
            for score, _source_id, document in ranked[:top_k]
        ]

    def _to_result(
        self,
        normalized_query: str,
        score: float,
        document: Dict[str, Any],
    ) -> Dict[str, Any]:
        content = document["content"]
        truncated = len(content) > self._max_content_chars
        metadata = deepcopy(document["metadata"])
        metadata.update(
            {
                "context_role": "untrusted_data",
                "truncated": truncated,
                "original_length": len(content),
            }
        )
        digest_input = f"{normalized_query}\n{document['source_id']}".encode("utf-8")
        retrieval_id = f"retrieval-{hashlib.sha256(digest_input).hexdigest()[:24]}"
        return {
            "retrieval_id": retrieval_id,
            "source_id": document["source_id"],
            "content": content[: self._max_content_chars],
            "score": score,
            "metadata": metadata,
        }


def _validate_query(query: str) -> str:
    if not isinstance(query, str):
        raise ValueError("query must be a string")
    normalized = " ".join(query.split())
    if not normalized:
        raise ValueError("query must not be empty")
    if len(normalized) > _MAX_QUERY_CHARS:
        raise ValueError(f"query must not exceed {_MAX_QUERY_CHARS} characters")
    return normalized


def _tokenize(value: str) -> Sequence[str]:
    return _TOKEN_PATTERN.findall(value.lower())
