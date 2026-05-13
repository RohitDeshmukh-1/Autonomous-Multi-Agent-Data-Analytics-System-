"""
agent/nodes/pandas_generator.py
Generates safe Pandas code for CSV/uploaded file analysis.
Supports multi-turn conversation context for follow-up queries.
"""

import re
from agent.state import AgentState
from llm import get_groq_client

SYSTEM = """You are an expert Python/Pandas data analyst.
Generate safe, executable Pandas code.
Rules:
- The DataFrame is already available as the variable `df`
- Output ONLY the Python code, no markdown fences, no explanation
- Store the final result in a variable called `result` — this must be a DataFrame or Series
- Never use: open(), exec(), eval(), __import__, os, sys, subprocess, requests, socket
- Never write files; never access the filesystem
- Keep code concise and efficient
- Use `.copy()` when modifying slices to avoid SettingWithCopyWarning
- If the user references a previous query (e.g. "filter that", "now group by"),
  use the conversation context to understand what "that" refers to"""


def _build_conversation_context(history: list) -> str:
    """Format recent conversation history for the prompt."""
    if not history:
        return "No prior conversation."

    lines = []
    for i, turn in enumerate(history[-3:], 1):
        lines.append(f"--- Turn {i} ---")
        lines.append(f"Question: {turn.get('query', '')}")
        if turn.get('code'):
            lines.append(f"Generated code: {turn['code']}")
        if turn.get('insight'):
            lines.append(f"Result summary: {turn['insight']}")
    return "\n".join(lines)


def pandas_generator(state: AgentState) -> AgentState:
    client = get_groq_client()

    conv_context = _build_conversation_context(
        state.get("conversation_history", [])
    )

    user_msg = (
        f"Schema:\n{state['schema_context']}\n\n"
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

    # Strip markdown fences
    code = re.sub(r"```(?:python)?", "", code).strip().rstrip("```").strip()

    return {**state, "generated_code": code, "code_type": "pandas"}
