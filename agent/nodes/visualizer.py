"""
agent/nodes/visualizer.py
Selects appropriate chart type and generates Plotly JSON spec from query results.
Pure Python — no LLM call for chart selection.
"""

from typing import Any, Dict, List, Optional
from agent.state import AgentState


def _infer_chart_type(result: List[Dict], user_query: str) -> str:
    """Heuristically pick chart type from result shape and query keywords."""
    if not result:
        return "table"

    keys = list(result[0].keys())
    n_cols = len(keys)
    n_rows = len(result)
    query_lower = user_query.lower()

    # Keyword overrides
    if any(w in query_lower for w in ["trend", "over time", "monthly", "yearly", "daily", "weekly"]):
        return "line"
    if any(w in query_lower for w in ["distribution", "histogram", "spread"]):
        return "histogram"
    if any(w in query_lower for w in ["proportion", "share", "percent", "breakdown"]):
        return "pie" if n_rows <= 8 else "bar"
    if any(w in query_lower for w in ["correlation", "scatter", "vs", "versus"]):
        return "scatter"

    # Shape-based defaults
    if n_cols == 2 and n_rows <= 20:
        return "bar"
    if n_cols == 2 and n_rows > 20:
        return "line"
    if n_cols >= 3:
        return "table"

    return "table"


def _build_plotly_spec(result: List[Dict], chart_type: str, user_query: str) -> Dict[str, Any]:
    if not result or chart_type == "table":
        return {
            "type": "table",
            "data": result[:200],
            "columns": list(result[0].keys()) if result else [],
        }

    keys = list(result[0].keys())
    x_key = keys[0]
    y_key = keys[1] if len(keys) > 1 else keys[0]

    x_vals = [row.get(x_key) for row in result]
    y_vals = [row.get(y_key) for row in result]

    if chart_type == "bar":
        data = [{"type": "bar", "x": x_vals, "y": y_vals, "name": y_key}]
    elif chart_type == "line":
        data = [{"type": "scatter", "mode": "lines+markers", "x": x_vals, "y": y_vals, "name": y_key}]
    elif chart_type == "pie":
        data = [{"type": "pie", "labels": x_vals, "values": y_vals}]
    elif chart_type == "scatter":
        data = [{"type": "scatter", "mode": "markers", "x": x_vals, "y": y_vals}]
    elif chart_type == "histogram":
        data = [{"type": "histogram", "x": y_vals, "name": y_key}]
    else:
        data = [{"type": "bar", "x": x_vals, "y": y_vals}]

    layout = {
        "title": user_query[:80],
        "xaxis": {"title": x_key},
        "yaxis": {"title": y_key},
        "template": "plotly_white",
        "margin": {"l": 60, "r": 20, "t": 50, "b": 60},
    }

    return {"plotly_json": {"data": data, "layout": layout}, "type": chart_type}


def visualizer(state: AgentState) -> AgentState:
    result = state.get("execution_result")
    if not result:
        return {**state, "chart_spec": None}

    chart_type = _infer_chart_type(result, state["user_query"])
    spec = _build_plotly_spec(result, chart_type, state["user_query"])

    return {**state, "chart_spec": spec}
