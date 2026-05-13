"""
agent/nodes/data_profiler.py
Natural language data profiling — generates a comprehensive dataset overview
including type inference, missing values, cardinality, distributions, and correlations.
"""

import math
from collections import Counter
from typing import Any, Dict, List, Optional

from connectors.base import get_connector


def _safe_float(val: Any) -> Optional[float]:
    try:
        return float(val)
    except (TypeError, ValueError):
        return None


def _basic_stats(values: List[float]) -> Dict[str, Any]:
    """Compute mean, median, min, max, std for a list of numbers."""
    if not values:
        return {}
    n = len(values)
    sorted_vals = sorted(values)
    mean = sum(values) / n
    median = sorted_vals[n // 2]
    variance = sum((x - mean) ** 2 for x in values) / n
    return {
        "count": n,
        "mean": round(mean, 2),
        "median": round(median, 2),
        "min": round(sorted_vals[0], 2),
        "max": round(sorted_vals[-1], 2),
        "std": round(math.sqrt(variance), 2),
    }


def _histogram_buckets(values: List[float], n_buckets: int = 8) -> List[Dict[str, Any]]:
    """Create histogram buckets for visualization."""
    if not values:
        return []
    min_val = min(values)
    max_val = max(values)
    if min_val == max_val:
        return [{"range": f"{min_val:.2f}", "count": len(values)}]

    step = (max_val - min_val) / n_buckets
    buckets = []
    for i in range(n_buckets):
        lo = min_val + i * step
        hi = lo + step
        count = sum(1 for v in values if lo <= v < hi) if i < n_buckets - 1 else sum(1 for v in values if lo <= v <= hi)
        buckets.append({
            "range": f"{lo:.1f}-{hi:.1f}",
            "count": count,
        })
    return buckets


def profile_connector(connector_id: str) -> Dict[str, Any]:
    """
    Generate a full data profile for a connector's data.
    Returns structured profile data suitable for rendering.
    """
    connector = get_connector(connector_id)
    schema = connector.get_schema()

    profile = {
        "connector_id": connector_id,
        "tables": [],
        "total_tables": len(schema),
        "total_columns": sum(len(t.get("columns", [])) for t in schema),
    }

    for table_info in schema[:10]:  # Cap at 10 tables
        table_name = table_info["table"]
        columns = table_info.get("columns", [])
        row_count = table_info.get("row_count", 0)

        # Sample data for profiling
        try:
            sample_sql = f'SELECT * FROM "{table_name}" LIMIT 1000'
            sample_data = connector.execute_sql(sample_sql)
        except Exception:
            sample_data = []

        col_profiles = []
        for col in columns:
            col_name = col["name"]
            col_type = col.get("type", "unknown")

            if not sample_data:
                col_profiles.append({
                    "name": col_name,
                    "type": col_type,
                    "null_count": 0,
                    "null_rate": 0,
                    "unique_count": 0,
                    "cardinality": "unknown",
                })
                continue

            raw_values = [row.get(col_name) for row in sample_data]
            null_count = sum(1 for v in raw_values if v is None)
            non_null = [v for v in raw_values if v is not None]
            unique_count = len(set(str(v) for v in non_null))

            col_profile: Dict[str, Any] = {
                "name": col_name,
                "type": col_type,
                "null_count": null_count,
                "null_rate": round(null_count / max(len(raw_values), 1), 3),
                "unique_count": unique_count,
                "cardinality": "high" if unique_count > len(non_null) * 0.8 else (
                    "medium" if unique_count > 10 else "low"
                ),
            }

            # Numeric stats
            float_values = [v for v in (_safe_float(x) for x in non_null) if v is not None]
            if float_values and len(float_values) > len(non_null) * 0.5:
                col_profile["stats"] = _basic_stats(float_values)
                col_profile["histogram"] = _histogram_buckets(float_values)
                col_profile["inferred_type"] = "numeric"
            else:
                # Categorical: top values
                str_values = [str(v) for v in non_null]
                top_values = Counter(str_values).most_common(5)
                col_profile["top_values"] = [
                    {"value": v, "count": c, "frequency": round(c / max(len(str_values), 1), 3)}
                    for v, c in top_values
                ]
                col_profile["inferred_type"] = "categorical"

            col_profiles.append(col_profile)

        # Compute correlations for numeric columns
        numeric_cols = [c for c in col_profiles if c.get("inferred_type") == "numeric"]
        correlations = []
        if len(numeric_cols) >= 2 and sample_data:
            for i in range(len(numeric_cols)):
                for j in range(i + 1, len(numeric_cols)):
                    col_a = numeric_cols[i]["name"]
                    col_b = numeric_cols[j]["name"]
                    vals_a = [_safe_float(r.get(col_a)) for r in sample_data]
                    vals_b = [_safe_float(r.get(col_b)) for r in sample_data]
                    paired = [(a, b) for a, b in zip(vals_a, vals_b) if a is not None and b is not None]
                    if len(paired) > 5:
                        corr = _pearson([p[0] for p in paired], [p[1] for p in paired])
                        if corr is not None and abs(corr) > 0.3:
                            correlations.append({
                                "column_a": col_a,
                                "column_b": col_b,
                                "correlation": round(corr, 3),
                                "strength": "strong" if abs(corr) > 0.7 else "moderate",
                            })

        profile["tables"].append({
            "name": table_name,
            "row_count": row_count,
            "column_count": len(columns),
            "columns": col_profiles,
            "correlations": correlations[:10],
        })

    return profile


def _pearson(x: List[float], y: List[float]) -> Optional[float]:
    """Compute Pearson correlation coefficient."""
    n = len(x)
    if n < 3:
        return None
    mean_x = sum(x) / n
    mean_y = sum(y) / n
    dx = [xi - mean_x for xi in x]
    dy = [yi - mean_y for yi in y]
    num = sum(a * b for a, b in zip(dx, dy))
    den_x = math.sqrt(sum(a ** 2 for a in dx))
    den_y = math.sqrt(sum(b ** 2 for b in dy))
    if den_x == 0 or den_y == 0:
        return None
    return num / (den_x * den_y)
