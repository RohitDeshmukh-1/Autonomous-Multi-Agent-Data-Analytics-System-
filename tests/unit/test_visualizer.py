"""
tests/unit/test_visualizer.py
Tests for chart type inference and Plotly spec generation.
Pure Python — no LLM or DB calls.
"""

import pytest
from agent.nodes.visualizer import visualizer, _infer_chart_type, _build_plotly_spec


# ── Chart type inference ──────────────────────────────────────────────────────

@pytest.mark.unit
class TestInferChartType:
    def test_trend_keyword_gives_line(self):
        rows = [{"month": "Jan", "count": 10}] * 5
        assert _infer_chart_type(rows, "show trend over time") == "line"

    def test_monthly_keyword_gives_line(self):
        rows = [{"month": "Jan", "revenue": 100}] * 12
        assert _infer_chart_type(rows, "monthly revenue breakdown") == "line"

    def test_proportion_keyword_few_rows_gives_pie(self):
        rows = [{"category": x, "pct": i * 10} for i, x in enumerate(["A", "B", "C"])]
        assert _infer_chart_type(rows, "proportion by category") == "pie"

    def test_proportion_many_rows_gives_bar(self):
        rows = [{"region": f"R{i}", "pct": i} for i in range(12)]
        assert _infer_chart_type(rows, "share by region") == "bar"

    def test_scatter_keyword(self):
        rows = [{"x": 1, "y": 2}] * 10
        assert _infer_chart_type(rows, "scatter plot of revenue vs orders") == "scatter"

    def test_two_columns_small_gives_bar(self):
        rows = [{"product": f"P{i}", "total": i * 100} for i in range(5)]
        assert _infer_chart_type(rows, "top products") == "bar"

    def test_many_columns_gives_table(self):
        rows = [{"a": 1, "b": 2, "c": 3, "d": 4}] * 5
        assert _infer_chart_type(rows, "summary") == "table"

    def test_empty_result_gives_table(self):
        assert _infer_chart_type([], "anything") == "table"

    def test_distribution_gives_histogram(self):
        rows = [{"amount": i * 10} for i in range(20)]
        assert _infer_chart_type(rows, "distribution of amounts") == "histogram"


# ── Plotly spec builder ───────────────────────────────────────────────────────

@pytest.mark.unit
class TestBuildPlotlySpec:
    def test_bar_spec_structure(self):
        rows = [{"product": "A", "total": 100}, {"product": "B", "total": 200}]
        spec = _build_plotly_spec(rows, "bar", "top products")
        assert spec["type"] == "bar"
        assert "plotly_json" in spec
        assert spec["plotly_json"]["data"][0]["type"] == "bar"

    def test_line_spec_structure(self):
        rows = [{"month": "Jan", "revenue": 1000}]
        spec = _build_plotly_spec(rows, "line", "monthly revenue")
        assert spec["plotly_json"]["data"][0]["mode"] == "lines+markers"

    def test_pie_spec_structure(self):
        rows = [{"category": "A", "pct": 60}, {"category": "B", "pct": 40}]
        spec = _build_plotly_spec(rows, "pie", "category share")
        assert spec["plotly_json"]["data"][0]["type"] == "pie"

    def test_table_spec_when_type_is_table(self):
        rows = [{"a": 1, "b": 2, "c": 3}]
        spec = _build_plotly_spec(rows, "table", "summary")
        assert spec["type"] == "table"
        assert spec["columns"] == ["a", "b", "c"]
        assert spec["data"] == rows

    def test_empty_result_gives_table(self):
        spec = _build_plotly_spec([], "bar", "test")
        assert spec["type"] == "table"

    def test_layout_has_title(self):
        rows = [{"x": 1, "y": 2}]
        spec = _build_plotly_spec(rows, "bar", "My Query Title")
        assert "My Query Title" in spec["plotly_json"]["layout"]["title"]

    def test_layout_uses_plotly_white_template(self):
        rows = [{"x": 1, "y": 2}]
        spec = _build_plotly_spec(rows, "bar", "test")
        assert spec["plotly_json"]["layout"]["template"] == "plotly_white"


# ── Visualizer node ───────────────────────────────────────────────────────────

@pytest.mark.unit
class TestVisualizerNode:
    def test_adds_chart_spec_to_state(self, sample_state, sample_rows):
        state = {**sample_state, "execution_result": sample_rows}
        result = visualizer(state)
        assert result["chart_spec"] is not None

    def test_no_result_gives_none_chart(self, sample_state):
        state = {**sample_state, "execution_result": None}
        result = visualizer(state)
        assert result["chart_spec"] is None

    def test_empty_result_gives_none_chart(self, sample_state):
        state = {**sample_state, "execution_result": []}
        result = visualizer(state)
        assert result["chart_spec"] is None

    def test_state_keys_preserved(self, sample_state, sample_rows):
        state = {**sample_state, "execution_result": sample_rows}
        result = visualizer(state)
        assert result["session_id"] == sample_state["session_id"]
        assert result["insight_text"] == sample_state["insight_text"]
