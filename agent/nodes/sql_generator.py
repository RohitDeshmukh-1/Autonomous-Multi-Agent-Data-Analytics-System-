"""
agent/nodes/sql_generator.py
Generates SQL using Groq llama-3.1-70b-versatile (code model).
Supports multi-turn conversation context for follow-up queries.
"""

import json
import re
from agent.state import AgentState
from llm import get_groq_client

SYSTEM = """You are an expert SQL analyst. Generate a single, syntactically correct SQL query.
Rules:
- Output ONLY the SQL query, no explanation, no markdown fences
- Use table and column names EXACTLY as provided in the schema
- Use standard SQL; prefer CTEs over nested subqueries for readability
- Never use DROP, DELETE, UPDATE, INSERT, ALTER, TRUNCATE, CREATE, GRANT
- Limit results to 500 rows unless the user asks for all
- For date math use standard SQL functions compatible with the dialect specified
- If the user references a previous query (e.g. "filter that", "break that down"),
  use the conversation context to understand what "that" refers to"""


def _build_conversation_context(history: list) -> str:
    """Format recent conversation history for the prompt."""
    if not history:
        return "No prior conversation."

    lines = []
    for i, turn in enumerate(history[-3:], 1):  # Last 3 turns
        lines.append(f"--- Turn {i} ---")
        lines.append(f"Question: {turn.get('query', '')}")
        if turn.get('code'):
            lines.append(f"Generated SQL: {turn['code']}")
        if turn.get('insight'):
            lines.append(f"Result summary: {turn['insight']}")
    return "\n".join(lines)


def sql_generator(state: AgentState) -> AgentState:
    client = get_groq_client()

    dialect = "postgres" if state["connector_id"].startswith(("neon", "postgres-enc")) else "sqlite"

    conv_context = _build_conversation_context(
        state.get("conversation_history", [])
    )

    user_msg = (
        f"Database dialect: {dialect}\n\n"
        f"Schema:\n{state['schema_context']}\n\n"
        f"Memory context:\n{state.get('memory_context', '')}\n\n"
        f"Conversation history:\n{conv_context}\n\n"
        f"User question: {state['user_query']}\n\n"
        f"Query plan: {state.get('query_plan', {}).get('approach', '')}"
    )

    code = client.complete_system(
        system=SYSTEM,
        user=user_msg,
        model=client.code_model,
        max_tokens=1024,
    )

    # Strip accidental markdown fences
    code = re.sub(r"```(?:sql)?", "", code).strip().rstrip("```").strip()

    return {
        **state,
        "generated_code": code,
        "code_type": "sql",
        "sql_dialect": dialect,
    }
