"""
agent/nodes/self_corrector.py
Attempts to fix generated code based on error class + original error message.
"""

import re
from agent.state import AgentState
from llm import get_groq_client

CORRECTION_PROMPTS = {
    "nonexistent_column": (
        "The code references a column that does not exist. "
        "Re-read the schema carefully and use ONLY the exact column names listed. "
        "Fix the column reference."
    ),
    "nonexistent_table": (
        "The code references a table that does not exist. "
        "Use ONLY the exact table names listed in the schema."
    ),
    "syntax": (
        "The code has a syntax error. Fix it while preserving the analytical intent."
    ),
    "type_mismatch": (
        "There is a type mismatch. Cast values appropriately (e.g., CAST(col AS TEXT))."
    ),
    "logic": (
        "The query logic is incorrect. Re-think the approach to answer the original question."
    ),
    "unknown": (
        "An unexpected error occurred. Rewrite the code from scratch to answer the question."
    ),
}

SYSTEM = """You are a code debugger. Fix the provided code based on the error and hint.
Output ONLY the corrected code — no explanation, no markdown fences."""


def self_corrector(state: AgentState) -> AgentState:
    attempts = state.get("correction_attempts", 0)
    max_attempts = state.get("max_corrections", 3)

    if attempts >= max_attempts:
        return {**state, "insight_text": "I was unable to answer this question after multiple attempts. Please try rephrasing."}

    error_class = state.get("error_class", "unknown")
    hint = CORRECTION_PROMPTS.get(error_class, CORRECTION_PROMPTS["unknown"])

    client = get_groq_client()
    user_msg = (
        f"Original question: {state['user_query']}\n"
        f"Schema:\n{state['schema_context']}\n\n"
        f"Failing code:\n{state['generated_code']}\n\n"
        f"Error: {state.get('execution_error', '')}\n\n"
        f"Fix hint: {hint}"
    )

    corrected = client.complete_system(
        system=SYSTEM,
        user=user_msg,
        model=client.code_model,
        max_tokens=1024,
    )
    corrected = re.sub(r"```(?:sql|python)?", "", corrected).strip().rstrip("```").strip()

    return {
        **state,
        "generated_code": corrected,
        "correction_attempts": attempts + 1,
        "execution_error": None,
    }
