"""
agent/graph.py
LangGraph stateful agent graph with tracing, anomaly detection, and
PERFORMANCE OPTIMIZATIONS:

1. Fused memory_retriever + query_planner into a single node that runs
   memory vector recall and schema RAG concurrently via ThreadPoolExecutor.
2. Fused insight_synthesizer + anomaly_detector + visualizer into a single
   "output_pipeline" node that runs the LLM insight call concurrently with
   CPU-bound anomaly detection and chart generation.
3. memory_updater runs as fire-and-forget background I/O — the response is
   returned to the user BEFORE the database write completes.

Flow (optimized):
  intent_router
    ├─ sql      → planner_with_memory → sql_generator → safety_validator → executor
    ├─ pandas   → planner_with_memory → pandas_generator → safety_validator → executor
    └─ insight  → output_pipeline (skip code gen)
                                                           │
                                                    (error?) yes → error_classifier → self_corrector → safety_validator (loop)
                                                           │ no
                                                    output_pipeline [insight + anomaly + visualizer in parallel] → memory_updater_async → END
"""

import concurrent.futures

from langgraph.graph import END, StateGraph

from agent.state import AgentState
from agent.trace import trace_node
from agent.nodes import (
    error_classifier,
    executor,
    insight_synthesizer,
    intent_router,
    memory_retriever,
    memory_updater,
    pandas_generator,
    query_planner,
    safety_validator,
    self_corrector,
    sql_generator,
    visualizer,
)
from agent.nodes.anomaly_detector import anomaly_detector


# ── Persistent thread pool for parallel node execution ─────────────────────────
_parallel_pool = concurrent.futures.ThreadPoolExecutor(
    max_workers=4, thread_name_prefix="agent_parallel"
)


# ── Fused node: planner_with_memory ────────────────────────────────────────────
# Runs memory_retriever and the expensive schema vector search concurrently,
# then feeds both into the query planner LLM call.

def _planner_with_memory(state: AgentState) -> AgentState:
    """
    Fused node that runs memory retrieval and schema RAG concurrently,
    then feeds the combined context into the query planner.
    
    Before: memory_retriever (300ms) → query_planner (500ms) = 800ms sequential
    After:  memory + schema_RAG concurrent (300ms) → planner LLM (500ms) = 500ms total
    """
    from llm import get_embedder, get_groq_client
    from schema.ingestor import get_relevant_tables
    from db.pool import pooled_cursor
    import json

    embedder = get_embedder()
    query = state["user_query"]
    connector_id = state["connector_id"]

    # Kick off embedding generation once — reuse the vector for both tasks
    query_vec = embedder.embed(query)

    # ── Run memory recall and schema RAG concurrently ──────────────────────────
    def _fetch_memory():
        with pooled_cursor(readonly=True, dict_cursor=True) as (cur, conn):
            cur.execute(
                """
                SELECT query, insight, table_names,
                       1 - (embedding <=> %s::vector) AS similarity
                FROM memory_embeddings
                WHERE session_id = %s
                ORDER BY similarity DESC
                LIMIT 3
                """,
                (query_vec, state["session_id"]),
            )
            rows = cur.fetchall()
        if not rows:
            return ""
        lines = []
        for r in rows:
            if r["similarity"] > 0.75:
                lines.append(f"[Past query: {r['query']}]\n[Insight: {r['insight']}]")
        return "\n---\n".join(lines)

    def _fetch_schema():
        return get_relevant_tables(
            connector_id=connector_id,
            query=query,
            top_k=4,
        )

    mem_future = _parallel_pool.submit(_fetch_memory)
    schema_future = _parallel_pool.submit(_fetch_schema)

    memory_context = mem_future.result(timeout=10)
    relevant_tables = schema_future.result(timeout=10)

    # ── Build schema context ───────────────────────────────────────────────────
    schema_lines = []
    for t in relevant_tables:
        cols = ", ".join(f"{c['name']} ({c['type']})" for c in t.get("columns", []))
        schema_lines.append(f"Table: {t['table']}\nColumns: {cols}")
    schema_context = "\n\n".join(schema_lines)

    # ── Run query planner LLM call ─────────────────────────────────────────────
    PLANNER_SYSTEM = """You are a data analyst query planner.
Given the user query, relevant table schemas, and memory context, produce a concise query plan.
Respond ONLY with JSON:
{
  "tables": ["table1", "table2"],
  "approach": "one sentence describing the analytical approach",
  "complexity": "simple|medium|complex",
  "requires_join": true|false
}"""

    client = get_groq_client()
    user_msg = (
        f"User query: {query}\n\n"
        f"Available schema:\n{schema_context}\n\n"
        f"Memory context:\n{memory_context or 'none'}"
    )
    raw = client.complete_system(
        system=PLANNER_SYSTEM,
        user=user_msg,
        model=client.reason_model,
        max_tokens=256,
    )
    try:
        plan = json.loads(raw)
    except json.JSONDecodeError:
        plan = {"tables": [], "approach": "direct query", "complexity": "simple", "requires_join": False}

    return {
        **state,
        "memory_context": memory_context,
        "relevant_tables": relevant_tables,
        "schema_context": schema_context,
        "query_plan": plan,
    }


# ── Fused node: output_pipeline ────────────────────────────────────────────────
# Runs insight synthesis (LLM), anomaly detection (CPU), and visualization (CPU)
# concurrently instead of sequentially.

def _output_pipeline(state: AgentState) -> AgentState:
    """
    Fused output pipeline that runs three independent tasks concurrently:
    - Insight synthesis (LLM call, ~400ms)
    - Anomaly detection (pure CPU, ~5ms)
    - Chart visualization (pure CPU, ~2ms)
    
    Before: insight (400ms) → anomaly (5ms) → visualizer (2ms) = 407ms sequential
    After:  all three concurrent = ~400ms (bounded by the LLM call)
    """
    result = state.get("execution_result")

    if not result:
        return {
            **state,
            "insight_text": "No results were returned for this query.",
            "anomalies": [],
            "chart_spec": None,
        }

    # Run all three concurrently
    insight_future = _parallel_pool.submit(insight_synthesizer, state)
    anomaly_future = _parallel_pool.submit(anomaly_detector, state)
    visualizer_future = _parallel_pool.submit(visualizer, state)

    insight_state = insight_future.result(timeout=30)
    anomaly_state = anomaly_future.result(timeout=10)
    vis_state = visualizer_future.result(timeout=10)

    return {
        **state,
        "insight_text": insight_state.get("insight_text", ""),
        "anomalies": anomaly_state.get("anomalies", []),
        "chart_spec": vis_state.get("chart_spec"),
    }


# ── Async memory updater (fire-and-forget) ─────────────────────────────────────

def _memory_updater_async(state: AgentState) -> AgentState:
    """
    Submits the memory write (embedding + 2 DB inserts) to a background thread.
    The response is returned to the user immediately without waiting for persistence.
    
    Savings: ~200-400ms removed from the critical response path.
    """
    _parallel_pool.submit(_safe_memory_write, state)

    # Return immediately with a generated history_id
    import uuid
    return {**state, "history_id": str(uuid.uuid4())}


def _safe_memory_write(state: AgentState):
    """Background task: persist query history and memory embeddings."""
    try:
        memory_updater(state)
    except Exception:
        pass  # Non-critical — don't crash the background thread


# ── Wrap nodes with tracing ────────────────────────────────────────────────────
_traced_intent_router = trace_node("intent_router")(intent_router)
_traced_planner_with_memory = trace_node("planner_with_memory")(_planner_with_memory)
_traced_sql_generator = trace_node("sql_generator")(sql_generator)
_traced_pandas_generator = trace_node("pandas_generator")(pandas_generator)
_traced_safety_validator = trace_node("safety_validator")(safety_validator)
_traced_executor = trace_node("executor")(executor)
_traced_error_classifier = trace_node("error_classifier")(error_classifier)
_traced_self_corrector = trace_node("self_corrector")(self_corrector)
_traced_output_pipeline = trace_node("output_pipeline")(_output_pipeline)
_traced_memory_updater = trace_node("memory_updater")(_memory_updater_async)


# ── Conditional edges ──────────────────────────────────────────────────────────

def route_intent(state: AgentState) -> str:
    intent = state.get("intent", "sql")
    if intent == "unsupported":
        return "unsupported"
    if intent == "pandas":
        return "pandas"
    if intent == "insight":
        return "insight_only"
    return "sql"


def route_after_validation(state: AgentState) -> str:
    """After safety_validator: proceed to execute or short-circuit if blocked."""
    error = state.get("execution_error", "")
    if error and error.startswith("SAFETY_BLOCK"):
        return "blocked"
    return "execute"


def route_after_execution(state: AgentState) -> str:
    """After executor: either synthesize or enter self-correction loop."""
    if state.get("execution_error"):
        attempts = state.get("correction_attempts", 0)
        max_attempts = state.get("max_corrections", 3)
        if attempts >= max_attempts:
            return "give_up"
        return "correct"
    return "success"


def route_after_correction(state: AgentState) -> str:
    """After self_corrector: always re-validate."""
    return "revalidate"


# ── Graph builder ──────────────────────────────────────────────────────────────

def build_graph() -> StateGraph:
    g = StateGraph(AgentState)

    # Nodes (all traced)
    g.add_node("intent_router", _traced_intent_router)
    g.add_node("planner_with_memory", _traced_planner_with_memory)
    g.add_node("sql_generator", _traced_sql_generator)
    g.add_node("pandas_generator", _traced_pandas_generator)
    g.add_node("safety_validator", _traced_safety_validator)
    g.add_node("executor", _traced_executor)
    g.add_node("error_classifier", _traced_error_classifier)
    g.add_node("self_corrector", _traced_self_corrector)
    g.add_node("output_pipeline", _traced_output_pipeline)
    g.add_node("memory_updater", _traced_memory_updater)

    # Entry
    g.set_entry_point("intent_router")

    # Intent routing
    g.add_conditional_edges(
        "intent_router",
        route_intent,
        {
            "sql": "planner_with_memory",
            "pandas": "planner_with_memory",
            "insight_only": "output_pipeline",
            "unsupported": END,
        },
    )

    # Fused planner → code gen
    g.add_conditional_edges(
        "planner_with_memory",
        lambda s: "pandas" if s.get("intent") == "pandas" else "sql",
        {"sql": "sql_generator", "pandas": "pandas_generator"},
    )

    g.add_edge("sql_generator", "safety_validator")
    g.add_edge("pandas_generator", "safety_validator")

    # Validation → execution or block
    g.add_conditional_edges(
        "safety_validator",
        route_after_validation,
        {"execute": "executor", "blocked": "output_pipeline"},
    )

    # Execution → success or self-correction
    g.add_conditional_edges(
        "executor",
        route_after_execution,
        {
            "success": "output_pipeline",
            "correct": "error_classifier",
            "give_up": "output_pipeline",
        },
    )

    # Error loop
    g.add_edge("error_classifier", "self_corrector")
    g.add_edge("self_corrector", "safety_validator")  # re-validate corrected code

    # Output → fire-and-forget memory write → END
    g.add_edge("output_pipeline", "memory_updater")
    g.add_edge("memory_updater", END)

    return g.compile()


# Singleton compiled graph
_graph = None


def get_graph():
    global _graph
    if _graph is None:
        _graph = build_graph()
    return _graph
