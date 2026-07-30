"""Shared score calculation and display helpers."""


def normalize_score(value):
    """Normalize a judge input to the system's 0.1-point unit."""
    return round(float(value), 1)


def trimmed_average(values):
    """Average all values for up to 3 judges; otherwise drop one high and low."""
    normalized = [normalize_score(value) for value in values]
    if not normalized:
        return 0.0
    if len(normalized) <= 3:
        return sum(normalized) / len(normalized)
    normalized.sort()
    valid = normalized[1:-1]
    return sum(valid) / len(valid)


def excluded_extreme_ids(scores_by_judge):
    """Return the judge IDs representing the one removed low and high score."""
    items = [
        (judge_id, normalize_score(value))
        for judge_id, value in scores_by_judge.items()
    ]
    if len(items) <= 3:
        return set()

    min_value = min(value for _, value in items)
    max_value = max(value for _, value in items)
    min_judge = next(judge_id for judge_id, value in items if value == min_value)
    max_judge = next(
        judge_id
        for judge_id, value in items
        if value == max_value and judge_id != min_judge
    )
    return {min_judge, max_judge}


def format_score(value):
    """Format all displayed aggregate scores consistently to three decimals."""
    try:
        return f"{float(value):.3f}"
    except (TypeError, ValueError):
        return str(value)
