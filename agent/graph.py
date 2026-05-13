"""
agent/graph.py
LangGraph stateful agent graph with tracing and anomaly detection.

Flow:
  intent_router
    ├─ sql      → memory_retriever → query_planner → sql_generator → safety_validator → executor
    ├─ pandas   → memory_retriever → query_planner → pandas_generator → safety_validator → executor
    └─ insight  → insight_synthesizer (skip code gen)
                                                           │
                                                    (error?) yes → error_classifier → self_corrector → safety_validator (loop)
                                                           │ no
                                                    insight_synthesizer → anomaly_detector → visualizer → memory_updater → END
"""

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


# ── Wrap all nodes with tracing ────────────────────────────────────────────────
_traced_intent_router = trace_node("intent_router")(intent_router)
_traced_memory_retriever = trace_node("memory_retriever")(memory_retriever)
_traced_query_planner = trace_node("query_planner")(query_planner)
_traced_sql_generator = trace_node("sql_generator")(sql_generator)
_traced_pandas_generator = trace_node("pandas_generator")(pandas_generator)
_traced_safety_validator = trace_node("safety_validator")(safety_validator)
_traced_executor = trace_node("executor")(executor)
_traced_error_classifier = trace_node("error_classifier")(error_classifier)
_traced_self_corrector = trace_node("self_corrector")(self_corrector)
_traced_insight_synthesizer = trace_node("insight_synthesizer")(insight_synthesizer)
_traced_anomaly_detector = trace_node("anomaly_detector")(anomaly_detector)
_traced_visualizer = trace_node("visualizer")(visualizer)
_traced_memory_updater = trace_node("memory_updater")(memory_updater)


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
    g.add_node("memory_retriever", _traced_memory_retriever)
    g.add_node("query_planner", _traced_query_planner)
    g.add_node("sql_generator", _traced_sql_generator)
    g.add_node("pandas_generator", _traced_pandas_generator)
    g.add_node("safety_validator", _traced_safety_validator)
    g.add_node("executor", _traced_executor)
    g.add_node("error_classifier", _traced_error_classifier)
    g.add_node("self_corrector", _traced_self_corrector)
    g.add_node("insight_synthesizer", _traced_insight_synthesizer)
    g.add_node("anomaly_detector", _traced_anomaly_detector)
    g.add_node("visualizer", _traced_visualizer)
    g.add_node("memory_updater", _traced_memory_updater)

    # Entry
    g.set_entry_point("intent_router")

    # Intent routing
    g.add_conditional_edges(
        "intent_router",
        route_intent,
        {
            "sql": "memory_retriever",
            "pandas": "memory_retriever",
            "insight_only": "insight_synthesizer",
            "unsupported": END,
        },
    )

    # Memory → planner → code gen
    g.add_edge("memory_retriever", "query_planner")

    g.add_conditional_edges(
        "query_planner",
        lambda s: "pandas" if s.get("intent") == "pandas" else "sql",
        {"sql": "sql_generator", "pandas": "pandas_generator"},
    )

    g.add_edge("sql_generator", "safety_validator")
    g.add_edge("pandas_generator", "safety_validator")

    # Validation → execution or block
    g.add_conditional_edges(
        "safety_validator",
        route_after_validation,
        {"execute": "executor", "blocked": "insight_synthesizer"},
    )

    # Execution → success or self-correction
    g.add_conditional_edges(
        "executor",
        route_after_execution,
        {
            "success": "insight_synthesizer",
            "correct": "error_classifier",
            "give_up": "insight_synthesizer",
        },
    )

    # Error loop
    g.add_edge("error_classifier", "self_corrector")
    g.add_edge("self_corrector", "safety_validator")  # re-validate corrected code

    # Output pipeline (insight → anomaly detection → visualizer → memory)
    g.add_edge("insight_synthesizer", "anomaly_detector")
    g.add_edge("anomaly_detector", "visualizer")
    g.add_edge("visualizer", "memory_updater")
    g.add_edge("memory_updater", END)

    return g.compile()


# Singleton compiled graph
_graph = None


def get_graph():
    global _graph
    if _graph is None:
        _graph = build_graph()
    return _graph
