"""
api/routers/query.py
POST /api/query/run        – run agent, return full result (with trace + anomalies)
POST /api/query/stream     – SSE stream with trace events + insight tokens
"""

import asyncio
import json
import time
import uuid
from typing import Any, AsyncGenerator, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from agent.graph import get_graph
from agent.state import AgentState
from agent.trace import AgentTracer, set_tracer, get_tracer
from agent.metrics import get_metrics_collector

router = APIRouter()

# ── In-memory conversation store (per session) ────────────────────────────────
_conversations: Dict[str, List[Dict[str, Any]]] = {}
_MAX_HISTORY = 5  # Keep last 5 turns per session


class QueryRequest(BaseModel):
    user_query: str = Field(..., min_length=1, max_length=2000)
    connector_id: str = Field(..., description="e.g. neon:public or csv:<url>")
    session_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str = Field(default="anonymous")


class TraceEventResponse(BaseModel):
    node: str
    status: str
    latency_ms: int = 0
    tokens_used: int = 0
    metadata: dict = {}


class QueryResponse(BaseModel):
    session_id: str
    intent: str
    generated_code: str
    code_type: str
    execution_result: list
    insight_text: str
    chart_spec: dict | None
    from_cache: bool
    latency_ms: int
    correction_attempts: int
    history_id: str | None
    anomalies: list = []
    trace: list = []


def _build_initial_state(req: QueryRequest) -> AgentState:
    # Inject conversation history for multi-turn context
    history = _conversations.get(req.session_id, [])

    return {
        "session_id": req.session_id,
        "user_id": req.user_id,
        "user_query": req.user_query,
        "connector_id": req.connector_id,
        "intent": "",
        "query_plan": {},
        "relevant_tables": [],
        "schema_context": "",
        "memory_context": "",
        "conversation_history": history,
        "generated_code": "",
        "code_type": "sql",
        "sql_dialect": "postgres",
        "execution_result": None,
        "execution_error": None,
        "from_cache": False,
        "error_class": None,
        "correction_attempts": 0,
        "max_corrections": 3,
        "insight_text": "",
        "chart_spec": None,
        "anomalies": [],
        "history_id": None,
        "latency_ms": None,
        "stream_tokens": [],
    }


def _update_conversation(session_id: str, result: dict):
    """Store this turn in conversation history for multi-turn context."""
    turn = {
        "query": result.get("user_query", ""),
        "code": result.get("generated_code", ""),
        "result_preview": json.dumps((result.get("execution_result") or [])[:5], default=str),
        "insight": result.get("insight_text", ""),
    }
    if session_id not in _conversations:
        _conversations[session_id] = []
    _conversations[session_id].append(turn)
    # Trim to max history
    if len(_conversations[session_id]) > _MAX_HISTORY:
        _conversations[session_id] = _conversations[session_id][-_MAX_HISTORY:]


@router.post("/run", response_model=QueryResponse)
async def run_query(req: QueryRequest):
    graph = get_graph()
    state = _build_initial_state(req)

    # Set up tracing
    tracer = AgentTracer()
    set_tracer(tracer)

    t0 = time.time()
    try:
        result = await asyncio.get_event_loop().run_in_executor(
            None, graph.invoke, state
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
    finally:
        set_tracer(None)

    total_ms = int((time.time() - t0) * 1000)

    # Update conversation history
    _update_conversation(req.session_id, result)

    # Record metrics
    metrics = get_metrics_collector()
    metrics.record_query(
        latency_ms=total_ms,
        from_cache=result.get("from_cache", False),
        correction_attempts=result.get("correction_attempts", 0),
        intent=result.get("intent", "sql"),
        error_class=result.get("error_class"),
    )

    return QueryResponse(
        session_id=result["session_id"],
        intent=result.get("intent", "sql"),
        generated_code=result.get("generated_code", ""),
        code_type=result.get("code_type", "sql"),
        execution_result=result.get("execution_result") or [],
        insight_text=result.get("insight_text", ""),
        chart_spec=result.get("chart_spec"),
        from_cache=result.get("from_cache", False),
        latency_ms=total_ms,
        correction_attempts=result.get("correction_attempts", 0),
        history_id=result.get("history_id"),
        anomalies=result.get("anomalies", []),
        trace=tracer.get_events(),
    )


async def _stream_insight(req: QueryRequest) -> AsyncGenerator[str, None]:
    """Run the agent, stream trace events live, then stream insight word-by-word."""
    graph = get_graph()
    state = _build_initial_state(req)

    # Set up tracing
    tracer = AgentTracer()
    set_tracer(tracer)

    t0 = time.time()
    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(None, graph.invoke, state)
    total_ms = int((time.time() - t0) * 1000)
    set_tracer(None)

    # Update conversation history
    _update_conversation(req.session_id, result)

    # Record metrics
    metrics = get_metrics_collector()
    metrics.record_query(
        latency_ms=total_ms,
        from_cache=result.get("from_cache", False),
        correction_attempts=result.get("correction_attempts", 0),
        intent=result.get("intent", "sql"),
        error_class=result.get("error_class"),
    )

    # Stream trace events first
    for trace_event in tracer.get_events():
        yield f"data: {json.dumps(trace_event)}\n\n"

    # Stream insight word by word
    insight = result.get("insight_text", "")
    for word in insight.split(" "):
        event = json.dumps({"token": word + " "})
        yield f"data: {event}\n\n"
        await asyncio.sleep(0.03)

    # Final event with full payload
    final = {
        "done": True,
        "chart_spec": result.get("chart_spec"),
        "generated_code": result.get("generated_code", ""),
        "code_type": result.get("code_type", "sql"),
        "execution_result": (result.get("execution_result") or [])[:20],
        "latency_ms": total_ms,
        "from_cache": result.get("from_cache", False),
        "history_id": result.get("history_id"),
        "anomalies": result.get("anomalies", []),
        "correction_attempts": result.get("correction_attempts", 0),
        "query_plan": result.get("query_plan", {}),
        "intent": result.get("intent", "sql"),
        "trace_summary": tracer.get_summary(),
    }
    yield f"data: {json.dumps(final, default=str)}\n\n"


@router.post("/stream")
async def stream_query(req: QueryRequest):
    return StreamingResponse(
        _stream_insight(req),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
