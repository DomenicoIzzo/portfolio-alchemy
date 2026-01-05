# engine/explain.py

from typing import Dict, Any, List
from eng.scoring import (
    score_quantitative_metric,
    score_qualitative_metric
)

def explain_company(
    row: Dict[str, Any],
    rules: Dict[str, Any],
    weights: Dict[str, float],
    qualitative_states: Dict[str, List[str]],
    penalties: Dict[str, Dict[str, float]],
) -> str:
    """
    Generate a detailed, human-readable explanation of the Dividend Grade
    calculation for a single company.
    """

    lines = []
    total_score = 0.0
    max_score = 0.0

    header = f"Dividend Grade explanation for {row.get('Company', 'N/A')} "
    header += f"({row.get('Ticker', 'N/A')})"
    lines.append(header)
    lines.append("=" * len(header))
    lines.append("")

    lines.append(
        f"Structure: {row.get('Strct')} | "
        f"GICS: {row.get('GICS')} | "
        f"Sub-sector: {row.get('Sub-sector', 'General')}"
    )
    lines.append("")

    # ----------------------------
    # Quantitative metrics
    # ----------------------------
    lines.append("1) Quantitative metrics assessment")
    lines.append("-" * 40)

    for metric, rule_value in rules.items():
        if metric not in weights:
            continue

        actual = row.get(metric)
        weight = weights.get(metric, 0.0)
        max_score += weight

        if actual is None or actual == "" or rule_value == "n.m.":
            lines.append(
                f"- {metric}: not meaningful for this structure → excluded"
            )
            continue

        threshold = parse_rule_value(rule_value)

        score, detail = score_quantitative_metric(
            metric_name=metric,
            actual_value=float(actual),
            rule_value=threshold,
            weight=weight,
            penalty_cfg=penalties.get(metric, {})
        )

        total_score += score

        lines.append(
            f"- {metric}: actual={actual}, rule={rule_value} "
            f"→ contribution={score:.2f} / {weight}"
        )
        lines.append(f"  {detail}")

    lines.append("")

    # ----------------------------
    # Qualitative metrics
    # ----------------------------
    lines.append("2) Qualitative metrics assessment")
    lines.append("-" * 40)

    for metric, states in qualitative_states.items():
        if metric not in weights:
            continue

        desired_state = rules.get(metric)
        actual_state = row.get(metric)
        weight = weights.get(metric, 0.0)
        max_score += weight

        if desired_state is None or desired_state == "n.m.":
            lines.append(
                f"- {metric}: not meaningful for this structure → excluded"
            )
            continue

        score, detail = score_qualitative_metric(
            metric_name=metric,
            actual_state=actual_state,
            desired_state=desired_state,
            ordered_states=states,
            weight=weight
        )

        total_score += score

        lines.append(
            f"- {metric}: actual='{actual_state}', target='{desired_state}' "
            f"→ contribution={score:.2f} / {weight}"
        )
        lines.append(f"  {detail}")

    lines.append("")

    # ----------------------------
    # Final normalization
    # ----------------------------
    lines.append("3) Final normalization")
    lines.append("-" * 40)

    if max_score > 0:
        normalized = 100 * total_score / max_score
    else:
        normalized = 0.0

    lines.append(f"Raw score: {total_score:.2f}")
    lines.append(f"Maximum possible score: {max_score:.2f}")
    lines.append(f"Normalized Dividend Safety score: {normalized:.1f} / 100")

    lines.append("")

    # ----------------------------
    # Interpretive summary
    # ----------------------------
    lines.append("4) Interpretive summary")
    lines.append("-" * 40)

    if normalized >= 80:
        interpretation = (
            "The dividend profile is structurally strong. "
            "Cash flow coverage, balance sheet strength, and payout discipline "
            "are well aligned with sector expectations."
        )
    elif normalized >= 60:
        interpretation = (
            "The dividend profile is generally sound, but some metrics "
            "show moderate pressure. Monitoring is recommended."
        )
    elif normalized >= 40:
        interpretation = (
            "The dividend exhibits elevated fragility. "
            "Sustainability depends on favorable conditions."
        )
    else:
        interpretation = (
            "The dividend profile is weak. "
            "Current distributions are not well supported by fundamentals."
        )

    lines.append(interpretation)

    return "\n".join(lines)

def explain_quantitative(metric, value, rule, weight, detail):
    return (
        f"[{metric}] value={value}, rule={rule}, "
        f"penalty={detail.get('penalty', 0):.2f}, "
        f"bonus={detail.get('bonus', 0)}, "
        f"score={detail.get('final', 0):.2f}/{weight}"
    )


def explain_qualitative(metric, value, desired, weight, detail):
    return (
        f"[{metric}] value='{value}', desired='{desired}', "
        f"rank={detail.get('rank')}, "
        f"score={detail.get('score', 0):.2f}/{weight}"
    )
