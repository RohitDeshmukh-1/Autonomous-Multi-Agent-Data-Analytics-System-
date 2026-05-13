"""
agent/nodes/anomaly_detector.py
Proactive anomaly detection — scans query results for statistical outliers,
null concentrations, distribution skew, and sudden spikes/drops.

Returns 'Did you know?' callouts below the chart.
"""

import math
from typing import Any, Dict, List, Optional

from agent.state import AgentState


def _safe_float(val: Any) -> Optional[float]:
    """Try to convert a value to float."""
    if val is None:
        return None
    try:
        return float(val)
    except (TypeError, ValueError):
        return None


def _detect_outliers(values: List[float], col_name: str) -> List[str]:
    """Z-score based outlier detection (|z| > 2)."""
    if len(values) < 5:
        return []

    mean = sum(values) / len(values)
    variance = sum((x - mean) ** 2 for x in values) / len(values)
    std = math.sqrt(variance) if variance > 0 else 0

    if std == 0:
        return []

    anomalies = []
    for v in values:
        z = abs((v - mean) / std)
        if z > 2.5:
            anomalies.append(
                f"📊 **Outlier detected** in `{col_name}`: value {v:,.2f} "
                f"is {z:.1f} standard deviations from the mean ({mean:,.2f})"
            )
            if len(anomalies) >= 3:
                break
    return anomalies


def _detect_null_concentration(data: List[Dict], total_rows: int) -> List[str]:
    """Flag columns with high null rates."""
    if not data or total_rows == 0:
        return []

    alerts = []
    cols = list(data[0].keys())
    for col in cols:
        nulls = sum(1 for row in data if row.get(col) is None)
        rate = nulls / total_rows
        if rate > 0.3 and nulls > 2:
            alerts.append(
                f"⚠️ **High null rate** in `{col}`: {rate:.0%} of values are missing "
                f"({nulls}/{total_rows} rows)"
            )
    return alerts


def _detect_spikes(values: List[float], col_name: str) -> List[str]:
    """Detect sudden spikes or drops in sequential data."""
    if len(values) < 4:
        return []

    alerts = []
    for i in range(1, len(values)):
        prev = values[i - 1]
        curr = values[i]
        if prev == 0:
            continue
        change = (curr - prev) / abs(prev)
        if abs(change) > 1.0:  # >100% change
            direction = "spike 📈" if change > 0 else "drop 📉"
            alerts.append(
                f"🔍 **Sudden {direction}** in `{col_name}`: "
                f"{prev:,.2f} → {curr:,.2f} ({change:+.0%} change)"
            )
            if len(alerts) >= 2:
                break
    return alerts


def _detect_concentration(values: List[float], col_name: str) -> List[str]:
    """Detect if a single value dominates the distribution."""
    if len(values) < 3:
        return []

    from collections import Counter
    rounded = [round(v, 2) for v in values]
    counts = Counter(rounded)
    most_common_val, most_common_count = counts.most_common(1)[0]
    ratio = most_common_count / len(values)

    if ratio > 0.5 and len(counts) > 1:
        return [
            f"🎯 **Concentration** in `{col_name}`: the value {most_common_val:,.2f} "
            f"appears in {ratio:.0%} of all rows"
        ]
    return []


def anomaly_detector(state: AgentState) -> AgentState:
    """
    Scan execution results for anomalies and add them to state.
    Runs after insight_synthesizer, before visualizer.
    """
    result = state.get("execution_result")
    if not result or len(result) < 3:
        return {**state, "anomalies": []}

    all_anomalies: List[str] = []
    cols = list(result[0].keys())

    for col in cols:
        raw_values = [row.get(col) for row in result]
        float_values = [v for v in (_safe_float(x) for x in raw_values) if v is not None]

        if len(float_values) < 3:
            continue

        # Run detectors
        all_anomalies.extend(_detect_outliers(float_values, col))
        all_anomalies.extend(_detect_spikes(float_values, col))
        all_anomalies.extend(_detect_concentration(float_values, col))

    # Null detection across all columns
    all_anomalies.extend(_detect_null_concentration(result, len(result)))

    # Cap at 5 most interesting anomalies
    return {**state, "anomalies": all_anomalies[:5]}
