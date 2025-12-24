def generate_insights(metrics: dict):
    insights = []

    velocity = metrics.get("velocity_change_pct")
    if velocity is not None and abs(velocity) >= 10:
        direction = "increased" if velocity > 0 else "decreased"
        insights.append(
            f"Team velocity {direction} by {abs(velocity)}% compared to the previous sprint."
        )

    if metrics.get("prs_stuck", 0) > 0:
        insights.append(
            "PR review delays were observed during the sprint."
        )

    if metrics.get("at_risk_jira", 0) > 0:
        insights.append(
            "At-risk Jira issues were identified that may affect sprint progress."
        )

    return insights[:3]


def confidence_score(metrics: dict):
    available = sum(1 for v in metrics.values() if v is not None)

    if available >= 4:
        return 92
    if available >= 2:
        return 78
    return 60
