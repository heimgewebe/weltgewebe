"""Fail-closed local embedding and deterministic hybrid-ranking core.

This module is deliberately independent from persistence, workers, HTTP routes and
web code. It accepts only pre-authorized synthetic search documents, binds every
vector to one immutable generation identity and falls back to lexical ranking only
for an explicit provider-availability failure.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
import unicodedata
from dataclasses import dataclass
from typing import Any, Mapping, Protocol, Sequence

NORMALIZATION_REVISION = "weltgewebe-search-normalization-v1"
RANKING_REVISION = "weltgewebe-hybrid-ranking-v1"
MAX_DIMENSIONS = 8192
MAX_CANDIDATES = 1000
MAX_TEXT_CHARACTERS = 65536
SEMANTIC_MINIMUM_COSINE = 0.55
SEMANTIC_MINIMUM_MARGIN = 0.015

RANK_EXACT_TITLE = 0
RANK_EXACT_TAG = 1
RANK_TITLE_PREFIX = 2
RANK_TYPO = 3
RANK_FULL_TEXT = 4
RANK_SEMANTIC = 5

STOP_WORDS = {
    "aber",
    "als",
    "am",
    "an",
    "auch",
    "auf",
    "aus",
    "bei",
    "bin",
    "bis",
    "das",
    "dass",
    "dem",
    "den",
    "der",
    "des",
    "die",
    "ein",
    "eine",
    "einem",
    "einen",
    "einer",
    "es",
    "etwas",
    "für",
    "gegen",
    "gemeinsam",
    "hat",
    "ich",
    "im",
    "in",
    "ist",
    "kann",
    "man",
    "mein",
    "meine",
    "mit",
    "möchte",
    "nach",
    "nicht",
    "nur",
    "oder",
    "ohne",
    "sich",
    "sie",
    "soll",
    "um",
    "und",
    "von",
    "vor",
    "was",
    "wenn",
    "wer",
    "wie",
    "will",
    "wir",
    "wo",
    "zu",
    "zum",
    "zur",
}

EMAIL_LIKE = re.compile(
    r"(?i)\b[a-z0-9.!#$%&'*+/=?^_`{|}~-]+@[a-z0-9-]+(?:\.[a-z0-9-]+)+\b"
)
PHONE_LIKE = re.compile(
    r"(?<![\w-])(?:\+49|0049|0[1-9]\d{1,4})(?:[ /-]?\d){6,14}(?![\w-])"
)
IPV4_LIKE = re.compile(
    r"(?<![\d.])(?:25[0-5]|2[0-4]\d|1?\d?\d)(?:\.(?:25[0-5]|2[0-4]\d|1?\d?\d)){3}(?![\d.])"
)


class SearchCoreError(ValueError):
    """Base class for deterministic search-core contract failures."""


class ProviderBoundaryError(SearchCoreError):
    """The provider is not a bound local provider or changed identity."""


class ProviderUnavailableError(SearchCoreError):
    """The bound local provider was temporarily unavailable."""


class VectorValidationError(SearchCoreError):
    """A vector violates dimension, finiteness or norm constraints."""


class GenerationMismatchError(SearchCoreError):
    """Vectors from different immutable generations were mixed."""


class PrivacyBoundaryError(SearchCoreError):
    """A query or document contains data outside the synthetic search boundary."""


def _canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def normalize_text(text: str) -> str:
    """Normalize index and query text through one versioned deterministic contract."""

    if not isinstance(text, str):
        raise SearchCoreError("text must be a string")
    value = unicodedata.normalize("NFKC", text).casefold()
    return " ".join(re.sub(r"[^\w]+", " ", value, flags=re.UNICODE).split())


def _require_text(value: Any, label: str, *, allow_empty: bool = False) -> str:
    if not isinstance(value, str):
        raise SearchCoreError(f"{label} must be a string")
    stripped = value.strip()
    if not allow_empty and not stripped:
        raise SearchCoreError(f"{label} must not be empty")
    if len(value) > MAX_TEXT_CHARACTERS:
        raise SearchCoreError(f"{label} exceeds {MAX_TEXT_CHARACTERS} characters")
    return value


def _reject_personal_data(texts: Sequence[str], label: str) -> None:
    for text in texts:
        if EMAIL_LIKE.search(text):
            raise PrivacyBoundaryError(f"{label} contains an email-like value")
        if PHONE_LIKE.search(text):
            raise PrivacyBoundaryError(f"{label} contains a phone-like value")
        if IPV4_LIKE.search(text):
            raise PrivacyBoundaryError(f"{label} contains an IPv4-like value")


@dataclass(frozen=True)
class ModelIdentity:
    provider: str
    model_id: str
    model_revision: str
    runtime_id: str
    dimensions: int

    def __post_init__(self) -> None:
        for label, value in (
            ("provider", self.provider),
            ("model_id", self.model_id),
            ("model_revision", self.model_revision),
            ("runtime_id", self.runtime_id),
        ):
            _require_text(value, label)
        if not self.provider.startswith("local:"):
            raise ProviderBoundaryError(
                "embedding provider must use the local: namespace"
            )
        if isinstance(self.dimensions, bool) or not isinstance(self.dimensions, int):
            raise VectorValidationError("embedding dimensions must be an integer")
        if not 1 <= self.dimensions <= MAX_DIMENSIONS:
            raise VectorValidationError(
                f"embedding dimensions must be between 1 and {MAX_DIMENSIONS}"
            )

    def as_dict(self) -> dict[str, Any]:
        return {
            "provider": self.provider,
            "model_id": self.model_id,
            "model_revision": self.model_revision,
            "runtime_id": self.runtime_id,
            "dimensions": self.dimensions,
        }


@dataclass(frozen=True)
class GenerationIdentity:
    generation_id: str
    model: ModelIdentity
    document_revision: str
    normalization_revision: str = NORMALIZATION_REVISION
    ranking_revision: str = RANKING_REVISION

    @staticmethod
    def derive_id(model: ModelIdentity, document_revision: str) -> str:
        _require_text(document_revision, "document_revision")
        payload = {
            "model": model.as_dict(),
            "document_revision": document_revision,
            "normalization_revision": NORMALIZATION_REVISION,
            "ranking_revision": RANKING_REVISION,
        }
        return (
            "search-gen-"
            + hashlib.sha256(_canonical_json(payload).encode("utf-8")).hexdigest()
        )

    @classmethod
    def build(
        cls, model: ModelIdentity, document_revision: str
    ) -> "GenerationIdentity":
        return cls(
            generation_id=cls.derive_id(model, document_revision),
            model=model,
            document_revision=document_revision,
        )

    def __post_init__(self) -> None:
        _require_text(self.document_revision, "document_revision")
        if self.normalization_revision != NORMALIZATION_REVISION:
            raise GenerationMismatchError(
                "normalization revision is not supported by this core"
            )
        if self.ranking_revision != RANKING_REVISION:
            raise GenerationMismatchError(
                "ranking revision is not supported by this core"
            )
        expected = self.derive_id(self.model, self.document_revision)
        if self.generation_id != expected:
            raise GenerationMismatchError(
                "generation id does not match its immutable identity"
            )

    def as_dict(self) -> dict[str, Any]:
        return {
            "generation_id": self.generation_id,
            "model": self.model.as_dict(),
            "document_revision": self.document_revision,
            "normalization_revision": self.normalization_revision,
            "ranking_revision": self.ranking_revision,
        }


@dataclass(frozen=True)
class SearchDocument:
    node_id: str
    title: str
    summary: str
    body: str
    tags: tuple[str, ...]
    kind: str
    language: str
    privacy_class: str = "synthetic"
    contains_personal_data: bool = False

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "SearchDocument":
        expected = {
            "node_id",
            "title",
            "summary",
            "body",
            "tags",
            "kind",
            "language",
            "privacy_class",
            "contains_personal_data",
        }
        if set(value) != expected:
            raise PrivacyBoundaryError(
                "search document must contain exactly the authorized search fields"
            )
        tags = value["tags"]
        if (
            not isinstance(tags, list)
            or not tags
            or len(tags) > 32
            or any(not isinstance(tag, str) for tag in tags)
        ):
            raise SearchCoreError("search document tags are invalid")
        return cls(
            node_id=value["node_id"],
            title=value["title"],
            summary=value["summary"],
            body=value["body"],
            tags=tuple(tags),
            kind=value["kind"],
            language=value["language"],
            privacy_class=value["privacy_class"],
            contains_personal_data=value["contains_personal_data"],
        )

    def __post_init__(self) -> None:
        for label, value in (
            ("node_id", self.node_id),
            ("title", self.title),
            ("summary", self.summary),
            ("body", self.body),
            ("kind", self.kind),
            ("language", self.language),
        ):
            _require_text(value, label, allow_empty=label in {"summary", "body"})
        if (
            self.privacy_class != "synthetic"
            or self.contains_personal_data is not False
        ):
            raise PrivacyBoundaryError(
                "search document must be explicitly synthetic and PII-free"
            )
        if not isinstance(self.tags, tuple):
            raise SearchCoreError("search document tags must be an immutable tuple")
        if len(self.tags) == 0 or len(self.tags) > 32:
            raise SearchCoreError("search document must contain between 1 and 32 tags")
        for tag in self.tags:
            _require_text(tag, "tag")
        _reject_personal_data(
            [
                self.node_id,
                self.title,
                self.summary,
                self.body,
                *self.tags,
                self.kind,
                self.language,
            ],
            "search document",
        )

    def embedding_text(self) -> str:
        return "\n".join(
            (
                f"Titel: {self.title}",
                f"Kurzbeschreibung: {self.summary}",
                f"Information: {self.body}",
                f"Tags: {', '.join(self.tags)}",
                f"Art: {self.kind}",
                f"Sprache: {self.language}",
            )
        )

    def content_sha256(self) -> str:
        payload = {
            "normalization_revision": NORMALIZATION_REVISION,
            "node_id": self.node_id,
            "title": normalize_text(self.title),
            "summary": normalize_text(self.summary),
            "body": normalize_text(self.body),
            "tags": [normalize_text(tag) for tag in self.tags],
            "kind": normalize_text(self.kind),
            "language": normalize_text(self.language),
        }
        return hashlib.sha256(_canonical_json(payload).encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class SearchQuery:
    text: str
    privacy_class: str = "synthetic"
    contains_personal_data: bool = False

    def __post_init__(self) -> None:
        _require_text(self.text, "query")
        if (
            self.privacy_class != "synthetic"
            or self.contains_personal_data is not False
        ):
            raise PrivacyBoundaryError(
                "search query must be explicitly synthetic and PII-free"
            )
        _reject_personal_data([self.text], "search query")

    def embedding_text(self) -> str:
        return (
            "Aufgabe: Finde den relevantesten sichtbaren Weltgewebe-Knoten.\nAnfrage: "
            + self.text
        )


@dataclass(frozen=True)
class BoundVector:
    generation_id: str
    values: tuple[float, ...]

    @classmethod
    def build(
        cls, generation: GenerationIdentity, values: Sequence[float]
    ) -> "BoundVector":
        return cls(
            generation_id=generation.generation_id,
            values=validate_vector(values, generation.model.dimensions),
        )


@dataclass(frozen=True)
class LexicalSignal:
    rank_class: int
    label: str
    score: float


@dataclass(frozen=True)
class RankingResult:
    ranked_node_ids: tuple[str, ...]
    mode: str
    generation: GenerationIdentity | None
    fallback_reason: str | None


class LocalEmbeddingProvider(Protocol):
    def identity(self) -> ModelIdentity: ...

    def embed(self, texts: Sequence[str]) -> Sequence[Sequence[float]]: ...


def validate_vector(
    values: Sequence[float], expected_dimensions: int
) -> tuple[float, ...]:
    if isinstance(expected_dimensions, bool) or not isinstance(
        expected_dimensions, int
    ):
        raise VectorValidationError("expected dimensions must be an integer")
    if not 1 <= expected_dimensions <= MAX_DIMENSIONS:
        raise VectorValidationError(
            "expected dimensions are outside the supported range"
        )
    if not isinstance(values, Sequence) or isinstance(values, (str, bytes)):
        raise VectorValidationError("embedding vector must be a numeric sequence")
    if len(values) != expected_dimensions:
        raise VectorValidationError("embedding vector dimension mismatch")
    converted: list[float] = []
    for value in values:
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise VectorValidationError("embedding vector contains a non-number")
        number = float(value)
        if not math.isfinite(number):
            raise VectorValidationError("embedding vector contains a non-finite value")
        converted.append(number)
    if math.sqrt(sum(value * value for value in converted)) == 0.0:
        raise VectorValidationError("embedding vector has zero norm")
    return tuple(converted)


def cosine_similarity(left: Sequence[float], right: Sequence[float]) -> float:
    if len(left) != len(right) or not left:
        raise VectorValidationError("cosine inputs have different or empty dimensions")
    numerator = sum(a * b for a, b in zip(left, right, strict=True))
    left_norm = math.sqrt(sum(value * value for value in left))
    right_norm = math.sqrt(sum(value * value for value in right))
    if left_norm == 0.0 or right_norm == 0.0:
        raise VectorValidationError("cosine input has zero norm")
    return numerator / (left_norm * right_norm)


def _tokens(text: str) -> set[str]:
    return {
        token
        for token in normalize_text(text).split()
        if len(token) >= 2 and token not in STOP_WORDS
    }


def _trigrams(text: str) -> set[str]:
    normalized = f"  {normalize_text(text)} "
    return {
        normalized[index : index + 3] for index in range(max(0, len(normalized) - 2))
    }


def _trigram_similarity(left: str, right: str) -> float:
    left_set = _trigrams(left)
    right_set = _trigrams(right)
    if not left_set or not right_set:
        return 0.0
    return len(left_set & right_set) / len(left_set | right_set)


def _full_text_score(query: str, document: SearchDocument) -> tuple[int, float]:
    query_tokens = _tokens(query)
    if not query_tokens:
        return 0, 0.0
    fields = (
        (_tokens(document.title), 4.0),
        (_tokens(" ".join(document.tags)), 3.0),
        (_tokens(document.summary), 2.0),
        (_tokens(document.kind), 2.0),
        (_tokens(document.body), 1.0),
    )
    matched: set[str] = set()
    weighted = 0.0
    for field_tokens, weight in fields:
        common = query_tokens & field_tokens
        matched.update(common)
        weighted += weight * len(common)
    required = 1 if len(query_tokens) <= 3 else 2
    if len(matched) < required:
        return len(matched), 0.0
    return len(matched), weighted / (4.0 * len(query_tokens))


def lexical_signal(
    query: SearchQuery, document: SearchDocument
) -> LexicalSignal | None:
    normalized_query = normalize_text(query.text)
    normalized_title = normalize_text(document.title)
    normalized_tags = {normalize_text(tag) for tag in document.tags}
    if normalized_title == normalized_query:
        return LexicalSignal(RANK_EXACT_TITLE, "exact_title", 1.0)
    if normalized_query in normalized_tags:
        return LexicalSignal(RANK_EXACT_TAG, "exact_tag", 1.0)
    if normalized_title.startswith(normalized_query):
        return LexicalSignal(
            RANK_TITLE_PREFIX,
            "title_prefix",
            len(normalized_query) / len(normalized_title),
        )

    typo_score = max(
        _trigram_similarity(query.text, document.title),
        _trigram_similarity(query.text, document.summary),
        *(_trigram_similarity(query.text, tag) for tag in document.tags),
    )
    if typo_score >= 0.30:
        return LexicalSignal(RANK_TYPO, "typo", typo_score)

    matched, full_text_score = _full_text_score(query.text, document)
    if matched and full_text_score > 0.0:
        return LexicalSignal(RANK_FULL_TEXT, "full_text", full_text_score)
    return None


def _validate_candidates(candidates: Sequence[SearchDocument]) -> None:
    if len(candidates) > MAX_CANDIDATES:
        raise SearchCoreError(f"candidate set exceeds {MAX_CANDIDATES}")
    node_ids = [candidate.node_id for candidate in candidates]
    if len(node_ids) != len(set(node_ids)):
        raise SearchCoreError("candidate node ids must be unique")


def _validate_precomputed_lexical(
    candidates: Sequence[SearchDocument], lexical_ranked_node_ids: Sequence[str]
) -> tuple[str, ...]:
    if isinstance(lexical_ranked_node_ids, (str, bytes)):
        raise SearchCoreError("precomputed lexical ranking must be a node-id sequence")
    ranked = tuple(lexical_ranked_node_ids)
    if len(ranked) != len(set(ranked)):
        raise SearchCoreError("precomputed lexical ranking contains duplicate node ids")
    candidate_ids = {item.node_id for item in candidates}
    if any(
        not isinstance(node_id, str) or node_id not in candidate_ids
        for node_id in ranked
    ):
        raise SearchCoreError(
            "precomputed lexical ranking exceeds the authorized candidate set"
        )
    return ranked


def rank_lexical(
    query: SearchQuery, candidates: Sequence[SearchDocument], *, limit: int = 10
) -> RankingResult:
    _validate_candidates(candidates)
    if not 1 <= limit <= 100:
        raise SearchCoreError("ranking limit must be between 1 and 100")
    scored: list[tuple[int, float, str]] = []
    for document in candidates:
        signal = lexical_signal(query, document)
        if signal is not None:
            scored.append((signal.rank_class, -signal.score, document.node_id))
    scored.sort()
    return RankingResult(
        ranked_node_ids=tuple(node_id for _, _, node_id in scored[:limit]),
        mode="lexical",
        generation=None,
        fallback_reason=None,
    )


def rank_hybrid(
    query: SearchQuery,
    candidates: Sequence[SearchDocument],
    generation: GenerationIdentity,
    query_vector: BoundVector,
    candidate_vectors: Mapping[str, BoundVector],
    *,
    lexical_ranked_node_ids: Sequence[str],
    limit: int = 10,
    semantic_minimum_cosine: float = SEMANTIC_MINIMUM_COSINE,
    semantic_minimum_margin: float = SEMANTIC_MINIMUM_MARGIN,
) -> RankingResult:
    _validate_candidates(candidates)
    if not 1 <= limit <= 100:
        raise SearchCoreError("ranking limit must be between 1 and 100")
    for label, value, lower, upper in (
        ("semantic_minimum_cosine", semantic_minimum_cosine, -1.0, 1.0),
        ("semantic_minimum_margin", semantic_minimum_margin, 0.0, 2.0),
    ):
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise SearchCoreError(f"{label} must be numeric")
        if not math.isfinite(float(value)) or not lower <= float(value) <= upper:
            raise SearchCoreError(f"{label} is outside the supported finite range")
    if query_vector.generation_id != generation.generation_id:
        raise GenerationMismatchError("query vector belongs to a different generation")
    query_values = validate_vector(query_vector.values, generation.model.dimensions)
    expected_ids = {document.node_id for document in candidates}
    if set(candidate_vectors) != expected_ids:
        raise GenerationMismatchError(
            "candidate vectors do not cover the exact authorized candidate set"
        )
    checked_vectors: dict[str, tuple[float, ...]] = {}
    for node_id, vector in candidate_vectors.items():
        if vector.generation_id != generation.generation_id:
            raise GenerationMismatchError(
                f"candidate vector {node_id!r} belongs to a different generation"
            )
        checked_vectors[node_id] = validate_vector(
            vector.values, generation.model.dimensions
        )

    lexical_ids = list(
        _validate_precomputed_lexical(candidates, lexical_ranked_node_ids)
    )

    lexical_set = set(lexical_ids)
    semantic: list[tuple[float, str]] = []
    for document in candidates:
        if document.node_id in lexical_set:
            continue
        score = cosine_similarity(query_values, checked_vectors[document.node_id])
        semantic.append((score, document.node_id))

    semantic.sort(key=lambda item: (-item[0], item[1]))
    semantic_ids: list[str] = []
    if semantic:
        top_score = semantic[0][0]
        runner_up = semantic[1][0] if len(semantic) > 1 else -1.0
        confident = (
            top_score >= semantic_minimum_cosine
            and top_score - runner_up >= semantic_minimum_margin
        )
        if confident:
            semantic_ids = [
                node_id
                for score, node_id in semantic
                if score >= semantic_minimum_cosine
            ]

    ranked = list(lexical_ids)
    ranked.extend(node_id for node_id in semantic_ids if node_id not in ranked)
    return RankingResult(
        ranked_node_ids=tuple(ranked[:limit]),
        mode="hybrid",
        generation=generation,
        fallback_reason=None,
    )


def embed_bound(
    provider: LocalEmbeddingProvider,
    documents: Sequence[SearchDocument],
    queries: Sequence[SearchQuery],
    *,
    document_revision: str,
) -> tuple[GenerationIdentity, dict[str, BoundVector], tuple[BoundVector, ...]]:
    _validate_candidates(documents)
    before = provider.identity()
    document_vectors = provider.embed(
        [document.embedding_text() for document in documents]
    )
    query_vectors = provider.embed([query.embedding_text() for query in queries])
    after = provider.identity()
    if before != after:
        raise ProviderBoundaryError(
            "embedding provider identity changed during one measurement"
        )
    if len(document_vectors) != len(documents) or len(query_vectors) != len(queries):
        raise VectorValidationError(
            "embedding provider returned an unexpected vector count"
        )
    generation = GenerationIdentity.build(before, document_revision)
    bound_documents = {
        document.node_id: BoundVector.build(generation, vector)
        for document, vector in zip(documents, document_vectors, strict=True)
    }
    bound_queries = tuple(
        BoundVector.build(generation, vector) for vector in query_vectors
    )
    return generation, bound_documents, bound_queries


def rank_with_provider(
    provider: LocalEmbeddingProvider,
    query: SearchQuery,
    candidates: Sequence[SearchDocument],
    *,
    document_revision: str,
    lexical_ranked_node_ids: Sequence[str],
    limit: int = 10,
) -> RankingResult:
    try:
        generation, document_vectors, query_vectors = embed_bound(
            provider,
            candidates,
            [query],
            document_revision=document_revision,
        )
    except ProviderUnavailableError as error:
        lexical_ids = _validate_precomputed_lexical(
            candidates, lexical_ranked_node_ids
        )[:limit]
        return RankingResult(
            ranked_node_ids=lexical_ids,
            mode="lexical_fallback",
            generation=None,
            fallback_reason=str(error),
        )
    return rank_hybrid(
        query,
        candidates,
        generation,
        query_vectors[0],
        document_vectors,
        lexical_ranked_node_ids=lexical_ranked_node_ids,
        limit=limit,
    )


DOES_NOT_ESTABLISH = (
    "production embedding model",
    "persistent vector storage",
    "pgvector availability",
    "projection worker",
    "backfill",
    "search API",
    "web search UI",
    "production deployment",
    "real-user relevance",
    "public live proof",
    "SemantAH archive authority",
)
