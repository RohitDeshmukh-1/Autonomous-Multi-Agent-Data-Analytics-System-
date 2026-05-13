"""
agent/nodes/safety_validator.py
AST-level SQL validation (sqlglot) + Python AST checks before execution.
"""

from agent.state import AgentState
from sandbox.sql_sandbox import validate_sql
from sandbox.python_sandbox import validate_python


def safety_validator(state: AgentState) -> AgentState:
    code = state["generated_code"]
    code_type = state["code_type"]

    if code_type == "sql":
        ok, error = validate_sql(code, dialect=state.get("sql_dialect", "postgres"))
    else:
        ok, error = validate_python(code)

    if not ok:
        return {
            **state,
            "execution_error": f"SAFETY_BLOCK: {error}",
            "execution_result": None,
        }

    return {**state, "execution_error": None}
