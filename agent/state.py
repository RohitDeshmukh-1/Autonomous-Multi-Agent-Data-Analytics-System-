"""
agent/state.py
LangGraph agent state — single TypedDict shared across all nodes.
"""

from typing import Any, Dict, List, Optional, TypedDict


class AgentState(TypedDict):
    # ── Input ──────────────────────────────────────────────────────────────────
    session_id: str
    user_id: str
    user_query: str
    connector_id: str          # neon:<schema> | sqlite:<supabase_url> | csv:<supabase_url>

    # ── Routing ────────────────────────────────────────────────────────────────
    intent: str                # sql | pandas | insight | unsupported
    query_plan: Dict[str, Any] # tables, approach, complexity

    # ── Schema context ─────────────────────────────────────────────────────────
    relevant_tables: List[Dict[str, Any]]   # [{table, columns, sample_rows}]
    schema_context: str                     # compressed text for prompts

    # ── Memory context ─────────────────────────────────────────────────────────
    memory_context: str        # retrieved similar past queries/insights

    # ── Multi-turn conversation context ────────────────────────────────────────
    conversation_history: List[Dict[str, Any]]  # [{query, code, result_preview, insight}]

    # ── Code generation ────────────────────────────────────────────────────────
    generated_code: str
    code_type: str             # sql | pandas
    sql_dialect: str           # postgres | sqlite

    # ── Execution ─────────────────────────────────────────────────────────────
    execution_result: Optional[List[Dict[str, Any]]]
    execution_error: Optional[str]
    from_cache: bool

    # ── Error handling ─────────────────────────────────────────────────────────
    error_class: Optional[str]         # nonexistent_column | syntax | logic | permission | unknown
    correction_attempts: int
    max_corrections: int               # default 3

    # ── Output ─────────────────────────────────────────────────────────────────
    insight_text: str
    chart_spec: Optional[Dict[str, Any]]   # Plotly JSON
    anomalies: List[str]                    # Proactive anomaly callouts

    # ── History / persistence ──────────────────────────────────────────────────
    history_id: Optional[str]
    latency_ms: Optional[int]
    stream_tokens: List[str]           # SSE partial tokens
