"""
agent/nodes/query_planner.py
Uses schema context + memory to decide which tables/columns to involve.
"""

import json
from agent.state import AgentState
from llm import get_groq_client
from schema.ingestor import get_relevant_tables

SYSTEM = """You are a data analyst query planner.
Given the user query, relevant table schemas, and memory context, produce a concise query plan.
Respond ONLY with JSON:
{
  "tables": ["table1", "table2"],
  "approach": "one sentence describing the analytical approach",
  "complexity": "simple|medium|complex",
  "requires_join": true|false
}"""


def query_planner(state: AgentState) -> AgentState:
    client = get_groq_client()

    # Retrieve relevant tables via vector search
    relevant_tables = get_relevant_tables(
        connector_id=state["connector_id"],
        query=state["user_query"],
        top_k=4,
    )

    # Build compressed schema text for the prompt
    schema_lines = []
    for t in relevant_tables:
        cols = ", ".join(
            f"{c['name']} ({c['type']})" for c in t.get("columns", [])
        )
        schema_lines.append(f"Table: {t['table']}\nColumns: {cols}")
    schema_context = "\n\n".join(schema_lines)

    user_msg = (
        f"User query: {state['user_query']}\n\n"
        f"Available schema:\n{schema_context}\n\n"
        f"Memory context:\n{state.get('memory_context', 'none')}"
    )

    raw = client.complete_system(
        system=SYSTEM,
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
        "query_plan": plan,
        "relevant_tables": relevant_tables,
        "schema_context": schema_context,
    }
