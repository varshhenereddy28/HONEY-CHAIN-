from __future__ import annotations

import math
from typing import Any

import numpy as np
from sklearn.ensemble import IsolationForest


def mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def zscore_value(value: float, values: list[float]) -> float:
    if not values:
        return 0.0
    avg = mean(values)
    variance = sum((v - avg) ** 2 for v in values) / len(values)
    std_dev = math.sqrt(variance)
    if std_dev == 0:
        return 0.0
    return abs(value - avg) / std_dev


def calculate_risk_score(batch: dict[str, Any], history: list[dict[str, Any]] | None = None) -> float:
    history = history or []
    risk = 0.0

    if history:
        quantities = [float(row.get("quantity_kg", 0.0)) for row in history]
        if quantities:
            spike_score = zscore_value(float(batch.get("quantity_kg", 0.0)), quantities)
            risk += min(0.55, spike_score / 4.0)

        apiary_counts: dict[str, int] = {}
        for row in history:
            key = str(row.get("apiary_id", "")).strip()
            if key:
                apiary_counts[key] = apiary_counts.get(key, 0) + 1
        current_apiary = str(batch.get("apiary_id", "")).strip()
        if current_apiary and apiary_counts.get(current_apiary, 0) > 0:
            risk += 0.15

    duplicate_signal = float(batch.get("duplicate_scan_count", 0.0))
    risk += min(0.3, duplicate_signal * 0.1)

    if batch.get("status") == "rejected":
        risk += 0.2

    return round(min(1.0, max(0.0, risk)), 3)


def anomaly_model_score(values: list[float], current_value: float) -> float:
    if len(values) < 3:
        return 0.0
    matrix = np.array(values + [current_value], dtype=float).reshape(-1, 1)
    model = IsolationForest(contamination=0.2, random_state=42)
    model.fit(matrix)
    decision = model.decision_function(np.array([[current_value]]))[0]
    return round(1.0 - max(0.0, min(1.0, (decision + 1.0) / 2.0)), 3)


def flag_fraud(batch: dict[str, Any], history: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    history = history or []
    risk_score = calculate_risk_score(batch, history)
    volume_values = [float(row.get("quantity_kg", 0.0)) for row in history]
    if volume_values:
        risk_score = max(risk_score, anomaly_model_score(volume_values, float(batch.get("quantity_kg", 0.0))))

    return {
        "risk_score": round(risk_score, 3),
        "status": "high-risk" if risk_score >= 0.7 else "watchlist" if risk_score >= 0.4 else "low-risk",
        "duplicate_scan_pattern": bool(float(batch.get("duplicate_scan_count", 0.0)) > 0),
    }
