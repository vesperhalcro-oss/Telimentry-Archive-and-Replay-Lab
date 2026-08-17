from __future__ import annotations

from typing import Any

import numpy as np

from backend.archive import list_missions, load_mission


def _series_from_mission(mission: dict[str, Any], field: str = "altitude_m") -> np.ndarray:
    values = [sample[field] for sample in mission.get("samples", [])]
    if not values:
        return np.array([0.0])
    return np.asarray(values, dtype=float)


def dtw_distance(a: np.ndarray, b: np.ndarray) -> float:
    """Simple O(n*m) DTW for prototype-scale mission traces."""
    n, m = len(a), len(b)
    cost = np.full((n + 1, m + 1), np.inf)
    cost[0, 0] = 0.0
    for i in range(1, n + 1):
        for j in range(1, m + 1):
            diff = abs(a[i - 1] - b[j - 1])
            cost[i, j] = diff + min(cost[i - 1, j], cost[i, j - 1], cost[i - 1, j - 1])
    return float(cost[n, m])


def match_score(reference: np.ndarray, candidate: np.ndarray) -> float:
    if len(reference) < 2 or len(candidate) < 2:
        return 0.0

    target_len = min(len(reference), len(candidate), 400)
    ref = np.interp(np.linspace(0, 1, target_len), np.linspace(0, 1, len(reference)), reference)
    cand = np.interp(np.linspace(0, 1, target_len), np.linspace(0, 1, len(candidate)), candidate)

    distance = dtw_distance(ref, cand)
    normalized = distance / (target_len * max(float(np.max(ref)), 1.0))
    score = max(0.0, min(100.0, 100.0 * (1.0 - normalized)))
    return round(score, 1)


def explain_match(reference: dict[str, Any], candidate: dict[str, Any], score: float) -> str:
    ref_anomaly = reference.get("has_anomaly", False)
    cand_anomaly = candidate.get("has_anomaly", False)
    if ref_anomaly and cand_anomaly:
        detail = "Parachute delay pattern"
    elif score >= 90:
        detail = "Altitude profile alignment"
    elif score >= 75:
        detail = "Similar ascent/descent curve"
    else:
        detail = "Partial trajectory overlap"
    return f"{score}% Match: {candidate.get('name')} — {detail}"


def find_similar_missions(
    reference_samples: list[dict[str, Any]],
    exclude_id: str | None = None,
    top_k: int = 5,
) -> list[dict[str, Any]]:
    reference = {"samples": reference_samples, "has_anomaly": any(s.get("anomaly") for s in reference_samples)}
    ref_series = _series_from_mission(reference)
    results: list[dict[str, Any]] = []

    for meta in list_missions():
        if exclude_id and meta["id"] == exclude_id:
            continue
        mission = load_mission(meta["id"])
        cand_series = _series_from_mission(mission)
        score = match_score(ref_series, cand_series)
        results.append(
            {
                "mission_id": meta["id"],
                "name": meta["name"],
                "rocket": meta["rocket"],
                "score": score,
                "summary": explain_match(reference, mission, score),
            }
        )

    results.sort(key=lambda item: item["score"], reverse=True)
    return results[:top_k]
