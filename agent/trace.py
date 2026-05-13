"""
agent/trace.py
Real-time agent execution tracing.

Collects timing, token usage, and status for each node in the LangGraph pipeline.
Trace events are streamed to the frontend via SSE for live pipeline visualization.
"""

import time
import threading
from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional


@dataclass
class TraceEvent:
    """A single trace event from a node execution."""
    node: str
    status: str  # "started" | "completed" | "failed"
    latency_ms: int = 0
    tokens_used: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["type"] = "trace"
        return d


class AgentTracer:
    """
    Collects trace events for a single agent run.
    Thread-safe for use across LangGraph nodes.
    """

    def __init__(self):
        self.events: List[TraceEvent] = []
        self._lock = threading.Lock()
        self._timers: Dict[str, float] = {}

    def start_node(self, node: str, metadata: Optional[Dict[str, Any]] = None):
        """Mark a node as started."""
        self._timers[node] = time.time()
        event = TraceEvent(
            node=node,
            status="started",
            metadata=metadata or {},
        )
        with self._lock:
            self.events.append(event)

    def end_node(
        self,
        node: str,
        tokens_used: int = 0,
        metadata: Optional[Dict[str, Any]] = None,
    ):
        """Mark a node as completed with timing info."""
        start = self._timers.pop(node, time.time())
        latency_ms = int((time.time() - start) * 1000)

        event = TraceEvent(
            node=node,
            status="completed",
            latency_ms=latency_ms,
            tokens_used=tokens_used,
            metadata=metadata or {},
        )
        with self._lock:
            self.events.append(event)

    def fail_node(self, node: str, error: str):
        """Mark a node as failed."""
        start = self._timers.pop(node, time.time())
        latency_ms = int((time.time() - start) * 1000)

        event = TraceEvent(
            node=node,
            status="failed",
            latency_ms=latency_ms,
            metadata={"error": error},
        )
        with self._lock:
            self.events.append(event)

    def get_events(self) -> List[Dict[str, Any]]:
        """Return all trace events as dicts."""
        with self._lock:
            return [e.to_dict() for e in self.events]

    def get_summary(self) -> Dict[str, Any]:
        """Return a summary of the trace."""
        with self._lock:
            total_ms = sum(e.latency_ms for e in self.events if e.status == "completed")
            total_tokens = sum(e.tokens_used for e in self.events if e.status == "completed")
            node_count = len([e for e in self.events if e.status == "completed"])
            failed = [e.node for e in self.events if e.status == "failed"]

            return {
                "total_latency_ms": total_ms,
                "total_tokens": total_tokens,
                "nodes_executed": node_count,
                "failed_nodes": failed,
                "events": [e.to_dict() for e in self.events],
            }


# ── Thread-local tracer storage ───────────────────────────────────────────────
_tracer_local = threading.local()


def set_tracer(tracer: AgentTracer):
    """Set the tracer for the current thread."""
    _tracer_local.tracer = tracer


def get_tracer() -> Optional[AgentTracer]:
    """Get the tracer for the current thread (may be None)."""
    return getattr(_tracer_local, "tracer", None)


def trace_node(node_name: str):
    """
    Decorator to automatically trace a node function.

    Usage:
        @trace_node("sql_generator")
        def sql_generator(state: AgentState) -> AgentState:
            ...
    """
    def decorator(func):
        def wrapper(state, *args, **kwargs):
            tracer = get_tracer()
            if tracer:
                tracer.start_node(node_name)
            try:
                result = func(state, *args, **kwargs)
                if tracer:
                    tracer.end_node(node_name)
                return result
            except Exception as e:
                if tracer:
                    tracer.fail_node(node_name, str(e))
                raise
        wrapper.__name__ = func.__name__
        return wrapper
    return decorator
