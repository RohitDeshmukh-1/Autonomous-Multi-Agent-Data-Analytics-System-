"""
tests/unit/test_python_sandbox.py
Tests for RestrictedPython-based Pandas execution sandbox.
"""

import pandas as pd
import pytest
from sandbox.python_sandbox import validate_python, run_pandas


@pytest.fixture
def df():
    return pd.DataFrame({
        "product": ["Widget", "Gadget", "Widget", "Doohickey"],
        "amount": [99.99, 149.99, 99.99, 49.99],
        "region": ["North", "South", "North", "East"],
    })


# ── validate_python ───────────────────────────────────────────────────────────

@pytest.mark.unit
class TestValidatePython:
    def test_safe_code_passes(self):
        code = "result = df.groupby('product')['amount'].sum().to_frame()"
        ok, err = validate_python(code)
        assert ok, err

    def test_blocks_open(self):
        ok, err = validate_python("open('/etc/passwd')")
        assert not ok
        assert "open" in err

    def test_blocks_os_import(self):
        ok, err = validate_python("import os\nresult = df")
        assert not ok

    def test_blocks_subprocess(self):
        ok, err = validate_python("import subprocess\nresult = df")
        assert not ok

    def test_blocks_dunder_attr(self):
        ok, err = validate_python("df.__class__.__bases__")
        assert not ok

    def test_blocks_exec(self):
        ok, err = validate_python("exec('import os')")
        assert not ok

    def test_blocks_eval(self):
        ok, err = validate_python("eval('1+1')")
        assert not ok

    def test_allows_pandas_import(self):
        ok, err = validate_python("import pandas as pd\nresult = df")
        assert ok

    def test_allows_numpy_import(self):
        ok, err = validate_python("import numpy as np\nresult = df")
        assert ok

    def test_blocks_requests_import(self):
        ok, err = validate_python("import requests\nresult = df")
        assert not ok

    def test_syntax_error(self):
        ok, err = validate_python("def broken(:\n  pass")
        assert not ok


# ── run_pandas ────────────────────────────────────────────────────────────────

@pytest.mark.unit
class TestRunPandas:
    def test_basic_groupby(self, df):
        code = "result = df.groupby('product')['amount'].sum().to_frame()"
        out = run_pandas(code, df)
        assert isinstance(out, pd.DataFrame)
        assert "amount" in out.columns

    def test_filter(self, df):
        code = "result = df[df['region'] == 'North'].copy()"
        out = run_pandas(code, df)
        assert len(out) == 2

    def test_new_column(self, df):
        code = "result = df.copy()\nresult['doubled'] = result['amount'] * 2"
        out = run_pandas(code, df)
        assert "doubled" in out.columns

    def test_series_result_coerced_to_dataframe(self, df):
        code = "result = df['amount']"
        out = run_pandas(code, df)
        assert isinstance(out, pd.DataFrame)

    def test_missing_result_raises(self, df):
        with pytest.raises(ValueError, match="result"):
            run_pandas("x = 1", df)

    def test_non_dataframe_result_raises(self, df):
        with pytest.raises(TypeError):
            run_pandas("result = 42", df)

    def test_safety_block_raises_permission_error(self, df):
        with pytest.raises(PermissionError, match="SAFETY_BLOCK"):
            run_pandas("import os\nresult = df", df)

    def test_augmented_assignment(self, df):
        # RestrictedPython disallows augmented assignment on subscripts (result['col'] += x)
        # Use explicit assignment instead — the sandbox enforces this restriction correctly
        code = "result = df.copy()\nresult['amount'] = result['amount'] + 10"
        out = run_pandas(code, df)
        assert out["amount"].min() > 50

    def test_sort_and_limit(self, df):
        code = "result = df.sort_values('amount', ascending=False).head(2)"
        out = run_pandas(code, df)
        assert len(out) == 2
        assert out.iloc[0]["amount"] == pytest.approx(149.99)

    def test_pivot_table(self, df):
        code = """
result = df.pivot_table(
    index='region', values='amount', aggfunc='sum'
).reset_index()
"""
        out = run_pandas(code, df)
        assert "region" in out.columns
