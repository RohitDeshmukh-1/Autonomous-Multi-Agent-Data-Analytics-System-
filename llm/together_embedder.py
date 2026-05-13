"""
llm/embedder.py
Local embedding using sentence-transformers (all-mpnet-base-v2 → 768-dim vectors).
Completely free — no API key required. Runs on CPU.
"""

import hashlib
from functools import lru_cache
from threading import Lock
from typing import Dict, List

from sentence_transformers import SentenceTransformer

# Model produces 768-dim vectors — matches existing pgvector schema
_MODEL_NAME = "all-mpnet-base-v2"
_lock = Lock()

# ── In-memory embedding cache (avoid re-computing identical strings) ──────────
_embed_cache: Dict[str, List[float]] = {}
_MAX_CACHE = 2048


def _cache_key(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()[:24]


class LocalEmbedder:
    def __init__(self):
        self._model = SentenceTransformer(_MODEL_NAME)

    def embed(self, text: str) -> List[float]:
        """Embed a single text string. Results are cached in-memory."""
        key = _cache_key(text)
        if key in _embed_cache:
            return _embed_cache[key]

        vec = self._model.encode(text, normalize_embeddings=True).tolist()

        with _lock:
            if len(_embed_cache) < _MAX_CACHE:
                _embed_cache[key] = vec
        return vec

    def embed_batch(self, texts: List[str]) -> List[List[float]]:
        """Embed multiple texts. Deduplicates and caches results."""
        # Check cache for each text
        results: List[List[float] | None] = []
        uncached_indices = []
        uncached_texts = []

        for i, t in enumerate(texts):
            key = _cache_key(t)
            if key in _embed_cache:
                results.append(_embed_cache[key])
            else:
                results.append(None)
                uncached_indices.append(i)
                uncached_texts.append(t)

        # Batch encode uncached texts
        if uncached_texts:
            vecs = self._model.encode(
                uncached_texts, normalize_embeddings=True, batch_size=32
            ).tolist()

            with _lock:
                for idx, text, vec in zip(uncached_indices, uncached_texts, vecs):
                    results[idx] = vec
                    key = _cache_key(text)
                    if len(_embed_cache) < _MAX_CACHE:
                        _embed_cache[key] = vec

        return results  # type: ignore


@lru_cache(maxsize=1)
def get_embedder() -> LocalEmbedder:
    return LocalEmbedder()
