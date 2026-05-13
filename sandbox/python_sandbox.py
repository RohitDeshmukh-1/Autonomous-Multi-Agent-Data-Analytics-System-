"""
sandbox/python_sandbox.py
RestrictedPython-based Pandas execution sandbox.
Validates and executes LLM-generated Pandas code safely.
"""

import ast
import io
from typing import Tuple

import pandas as pd
from RestrictedPython import compile_restricted, safe_globals
from RestrictedPython.Guards import (
    guarded_iter_unpack_sequence,
    guarded_unpack_sequence,
    safe_builtins,
)

# Modules the sandbox is allowed to import
_ALLOWED_IMPORTS = {"pandas", "numpy", "math", "statistics", "datetime", "json", "re"}

# AST-level forbidden patterns (extra layer before RestrictedPython)
_FORBIDDEN_NAMES = {
    "open", "exec", "eval", "__import__", "compile",
    "os", "sys", "subprocess", "socket", "requests",
    "importlib", "builtins", "__builtins__", "globals", "locals",
    "getattr", "setattr", "delattr", "vars", "dir",
}


def validate_python(code: str) -> Tuple[bool, str]:
    """AST-level check before RestrictedPython compilation."""
    try:
        tree = ast.parse(code)
    except SyntaxError as e:
        return False, f"Syntax error: {e}"

    for node in ast.walk(tree):
        # Block dangerous names
        if isinstance(node, ast.Name) and node.id in _FORBIDDEN_NAMES:
            return False, f"Forbidden name: {node.id}"
        if isinstance(node, ast.Attribute) and node.attr.startswith("__"):
            return False, f"Forbidden dunder attribute: {node.attr}"
        # Block imports of non-whitelisted modules
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            names = (
                [a.name for a in node.names]
                if isinstance(node, ast.Import)
                else [node.module or ""]
            )
            for name in names:
                top = name.split(".")[0]
                if top not in _ALLOWED_IMPORTS:
                    return False, f"Forbidden import: {name}"

    return True, ""


def run_pandas(code: str, df: pd.DataFrame) -> pd.DataFrame:
    """
    Execute LLM-generated Pandas code in a RestrictedPython sandbox.
    `df` is injected; result must be stored in variable `result`.
    Returns a DataFrame.
    """
    ok, err = validate_python(code)
    if not ok:
        raise PermissionError(f"SAFETY_BLOCK: {err}")

    try:
        byte_code = compile_restricted(code, filename="<sandbox>", mode="exec")
    except SyntaxError as e:
        raise SyntaxError(f"Compile error: {e}") from e

    restricted_builtins = safe_builtins.copy()
    restricted_builtins["__import__"] = _safe_import

    def _getitem_(obj, key):
        return obj[key]

    def _write_(obj):
        return obj

    glb = {
        **safe_globals,
        "__builtins__": restricted_builtins,
        "_getiter_": iter,
        "_getitem_": _getitem_,
        "_getattr_": getattr,
        "_write_": _write_,
        "_inplacevar_": _inplace_var,
        "_iter_unpack_sequence_": guarded_iter_unpack_sequence,
        "_unpack_sequence_": guarded_unpack_sequence,
        "df": df,
        "pd": pd,
    }
    loc: dict = {}

    exec(byte_code, glb, loc)  # noqa: S102

    result = loc.get("result")
    if result is None:
        raise ValueError("Code did not set a `result` variable")
    if isinstance(result, pd.Series):
        result = result.to_frame()
    if not isinstance(result, pd.DataFrame):
        raise TypeError(f"`result` must be a DataFrame, got {type(result)}")

    return result


def _safe_import(name, *args, **kwargs):
    top = name.split(".")[0]
    if top not in _ALLOWED_IMPORTS:
        raise ImportError(f"Import of '{name}' is not allowed in the sandbox")
    return __import__(name, *args, **kwargs)


def _inplace_var(op, x, y):
    """Handle augmented assignment (+=, -= etc.) inside RestrictedPython."""
    if op == "+=":
        return x + y
    if op == "-=":
        return x - y
    if op == "*=":
        return x * y
    if op == "/=":
        return x / y
    return x
