from app.models.result_model import Violation, CategoryScore

CATEGORY_WEIGHTS = {
    "STRUCTURE": 0.30,
    "TYPOGRAPHY": 0.20,
    "PAGE_LAYOUT": 0.15,
    "PARAGRAPH_FORMATTING": 0.15,
    "FIGURES_TABLES": 0.10,
    "CAPTIONS_NUMBERING": 0.05,
    "HEADER_FOOTER": 0.05,
}
SEVERITY_PENALTY_WEIGHT = {"ERROR": 1.0, "WARNING": 0.4, "INFO": 0.0}


def compute_scores(violations: list[Violation], category_check_counts: dict[str, int]):
    by_category: dict[str, list[Violation]] = {c: [] for c in CATEGORY_WEIGHTS}
    for v in violations:
        by_category.setdefault(v.category, []).append(v)

    category_scores: list[CategoryScore] = []
    weighted_sum = 0.0
    weight_total = 0.0

    for category, weight in CATEGORY_WEIGHTS.items():
        cat_violations = by_category.get(category, [])
        checks = category_check_counts.get(category, 0)
        raw_penalty = sum(
            SEVERITY_PENALTY_WEIGHT[v.severity.value] * v.affected_count
            for v in cat_violations
        )
        if checks > 0:
            score = max(0.0, 1 - (raw_penalty / checks)) * 100
        else:
            score = 0.0  # clients display Not checked when checks_performed is zero
        error_count = sum(v.affected_count for v in cat_violations if v.severity.value == "ERROR")
        warning_count = sum(v.affected_count for v in cat_violations if v.severity.value == "WARNING")
        category_scores.append(CategoryScore(
            category=category, score=round(score, 1), checks_performed=checks,
            error_count=error_count, warning_count=warning_count,
        ))
        if checks > 0:
            weighted_sum += score * weight
            weight_total += weight

    overall = weighted_sum / weight_total if weight_total else 0.0
    return round(overall, 1), category_scores
