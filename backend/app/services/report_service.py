from typing import Any


RATING_SCORES = {
    "Deep": 1.0,
    "Moderate": 0.75,
    "Shallow": 0.5,
    "Missing": 0.0,
    "Comprehensive": 1.0,
    "Adequate": 0.75,
    "Limited": 0.5,
    "Insufficient": 0.0,
    "Expert": 1.0,
    "Competent": 0.75,
    "Basic": 0.5,
    "Flawed": 0.0,
    "Precise": 1.0,
    "Good": 0.75,
    "Acceptable": 0.5,
    "Poor": 0.0,
    "Optimal": 1.0,
    "Efficient": 0.75,
    "Wasteful": 0.0,
    "Excellent": 1.0,
    "Fair": 0.5,
}

DEFAULT_WEIGHTS = {
    "vulnerability_understanding": 0.17,
    "reconnaissance_thoroughness": 0.17,
    "exploitation_methodology": 0.17,
    "technical_accuracy": 0.17,
    "efficiency_approach": 0.16,
    "adaptability": 0.16,
}


def build_ctfjudge_report(
    value: Any,
    weights: dict[str, float] | None = None,
    retrieval_results: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError("CTFJudge report input must be an object")
    matrix = value.get("competency_matrix")
    if not isinstance(matrix, dict):
        raise ValueError("CTFJudge report requires a competency_matrix object")

    selected_weights = weights or DEFAULT_WEIGHTS
    if set(selected_weights) != set(DEFAULT_WEIGHTS):
        raise ValueError("Formula weights must contain exactly the six CTFJudge competencies")
    if abs(sum(selected_weights.values()) - 1.0) > 0.0001:
        raise ValueError("Formula weights must sum to 1.0")

    breakdown: dict[str, Any] = {}
    overall_score = 0.0
    for competency, weight in selected_weights.items():
        rating = matrix.get(competency)
        if rating not in RATING_SCORES:
            raise ValueError(f"Unsupported rating '{rating}' for competency '{competency}'")
        score = RATING_SCORES[rating]
        weighted_score = score * weight
        overall_score += weighted_score
        breakdown[competency] = {
            "rating": rating,
            "score": score,
            "weight": weight,
            "weighted_score": round(weighted_score, 4),
        }

    comparisons = _ground_comparisons(value.get("comparisons"), retrieval_results)
    return {
        **value,
        "comparisons": comparisons,
        "overall_score": round(overall_score, 3),
        "formula_breakdown": breakdown,
    }


def normalize_score(value: Any) -> float:
    try:
        score = float(value)
    except (TypeError, ValueError):
        return 0.0
    if score > 1 and score <= 10:
        score /= 10
    elif score > 10:
        score /= 100
    return round(max(0.0, min(score, 1.0)), 3)


def _ground_comparisons(
    comparisons: Any,
    retrieval_results: list[dict[str, Any]] | None,
) -> list[dict[str, Any]]:
    ai_items = comparisons if isinstance(comparisons, list) else []
    by_id = {
        str(item.get("student_chunk_id")): item
        for item in ai_items
        if isinstance(item, dict) and item.get("student_chunk_id") is not None
    }
    if retrieval_results is None:
        return [
            {**item, "score": normalize_score(item.get("score"))}
            for item in ai_items
            if isinstance(item, dict)
        ]

    grounded: list[dict[str, Any]] = []
    for retrieval in retrieval_results:
        chunk_id = str(retrieval.get("student_chunk_id", ""))
        ai_item = by_id.get(chunk_id, {})
        candidates = retrieval.get("candidates")
        matches = [
            {
                "chunk_id": str(candidate.get("golden_chunk_id", "")),
                "content": str(candidate.get("content", "")),
                "similarity_score": normalize_score(candidate.get("similarity_score")),
            }
            for candidate in (candidates if isinstance(candidates, list) else [])
            if isinstance(candidate, dict)
        ]
        grounded.append(
            {
                "student_chunk_id": chunk_id,
                "student_content": str(retrieval.get("student_content", "")),
                "classification": str(ai_item.get("classification", "no_match")),
                "score": normalize_score(ai_item.get("score")),
                "explanation": str(
                    ai_item.get("explanation", "AI chưa trả về đánh giá cho trích dẫn này.")
                ),
                "matched_golden": matches,
            }
        )
    return grounded
