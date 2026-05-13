"""
agent/nodes/error_classifier.py
Classifies execution errors into actionable categories for self-correction.
"""

import json
from agent.state import AgentState
from llm import get_groq_client

ERROR_CLASSES = [
    "nonexistent_column",   # column name hallucinated
    "nonexistent_table",    # table name hallucinated
    "syntax",               # malformed SQL/Python syntax
    "type_mismatch",        # wrong type comparison
    "logic",                # correct syntax but wrong logic
    "permission",           # blocked by safety validator
    "unknown",
]

SYSTEM = f"""Classify this database/code execution error into one of these categories:
{', '.join(ERROR_CLASSES)}
Respond ONLY with JSON: {{"error_class": "<class>", "hint": "<what to fix>"}}"""


def error_classifier(state: AgentState) -> AgentState:
    error = state.get("execution_error", "")
    if not error:
        return state

    client = get_groq_client()
    raw = client.complete_system(
        system=SYSTEM,
        user=f"Error: {error}\nGenerated code:\n{state['generated_code']}",
        model=client.reason_model,
        max_tokens=128,
    )
    try:
        result = json.loads(raw)
        error_class = result.get("error_class", "unknown")
    except json.JSONDecodeError:
        error_class = "unknown"

    return {**state, "error_class": error_class}
