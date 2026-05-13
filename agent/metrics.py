"""
agent/metrics.py
In-memory metrics collector for observability.

Tracks query latencies, cache hit ratios, self-correction rates,
token usage, and error distributions. Exposed via /api/metrics.
"""

import time
import threading
from collections import defaultdict
from typing import Any, Dict, List


class MetricsCollector:
    """Thread-safe metrics collector for the agent pipeline."""

    def __init__(self):
        self._lock = threading.Lock()
        self._latencies: List[int] = []  # ms
        self._cache_hits = 0
        self._cache_misses = 0
        self._total_queries = 0
        self._correction_counts: List[int] = []
        self._token_usage: List[int] = []
        self._errors: Dict[str, int] = defaultdict(int)
        self._intents: Dict[str, int] = defaultdict(int)
        self._start_time = time.time()

    def record_query(
        self,
        latency_ms: int,
        from_cache: bool,
        correction_attempts: int,
        intent: str,
        tokens_used: int = 0,
        error_class: str = None,
    ):
        with self._lock:
            self._total_queries += 1
            self._latencies.append(latency_ms)
            self._correction_counts.append(correction_attempts)
            self._token_usage.append(tokens_used)
            self._intents[intent] += 1

            if from_cache:
                self._cache_hits += 1
            else:
                self._cache_misses += 1

            if error_class:
                self._errors[error_class] += 1

    def get_metrics(self) -> Dict[str, Any]:
        with self._lock:
            latencies = sorted(self._latencies) if self._latencies else [0]
            n = len(latencies)
            uptime_s = int(time.time() - self._start_time)

            return {
                "uptime_seconds": uptime_s,
                "total_queries": self._total_queries,
                "latency": {
                    "p50_ms": latencies[n // 2] if n else 0,
                    "p95_ms": latencies[int(n * 0.95)] if n else 0,
                    "p99_ms": latencies[int(n * 0.99)] if n else 0,
                    "avg_ms": sum(latencies) // max(n, 1),
                },
                "cache": {
                    "hits": self._cache_hits,
                    "misses": self._cache_misses,
                    "hit_ratio": round(
                        self._cache_hits / max(self._cache_hits + self._cache_misses, 1), 3
                    ),
                },
                "self_correction": {
                    "avg_retries": round(
                        sum(self._correction_counts) / max(len(self._correction_counts), 1), 2
                    ),
                    "queries_needing_correction": sum(1 for c in self._correction_counts if c > 0),
                    "correction_rate": round(
                        sum(1 for c in self._correction_counts if c > 0)
                        / max(self._total_queries, 1),
                        3,
                    ),
                },
                "tokens": {
                    "total": sum(self._token_usage),
                    "avg_per_query": sum(self._token_usage) // max(self._total_queries, 1),
                },
                "intents": dict(self._intents),
                "errors": dict(self._errors),
            }


# ── Singleton ─────────────────────────────────────────────────────────────────
_metrics = None


def get_metrics_collector() -> MetricsCollector:
    global _metrics
    if _metrics is None:
        _metrics = MetricsCollector()
    return _metrics
