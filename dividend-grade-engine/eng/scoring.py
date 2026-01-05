import math


# ---------------------------------------------------------
# Quantitative scoring
# ---------------------------------------------------------

def score_quantitative_metric(metric, value, rule, weight, penalty_cfg):
    """
    Quantitative scoring with:
    - coherent % parsing
    - convex penalties
    - structural kill-switch
    - bounded bonus
    """

    if value is None or rule in ("n.m.", "", None):
        return 0.0, {"reason": "missing"}

    # ----------------------------
    # PARSE RULE
    # ----------------------------
    rule = str(rule).strip()
    rule_is_percent = rule.endswith("%")
    rule_num = float(rule.strip("<>%")) / (100 if rule_is_percent else 1)

    # ----------------------------
    # PARSE VALUE
    # ----------------------------
    value = str(value).strip()
    value_is_percent = value.endswith("%")
    value_num = float(value.strip("%")) / (100 if value_is_percent else 1)

    metric_type = penalty_cfg["type"]      # "min" or "max"
    soft = penalty_cfg["soft_buffer"]
    hard = penalty_cfg["hard_limit"]
    slope = penalty_cfg["penalty_slope"]
    max_penalty = penalty_cfg["max_penalty"]
    bonus = penalty_cfg.get("bonus", 0)

    penalty = 0.0
    applied_bonus = 0.0

    # ----------------------------
    # STRUCTURAL KILL SWITCH
    # ----------------------------
    if metric in ("CFPR", "FCFPR") and value_num > rule_num * 2.0:
        return 0.0, {
            "penalty": max_penalty,
            "bonus": 0,
            "raw": 0,
            "max": weight,
            "kill_switch": True
        }

    if metric in ("NDtE", "NDtC") and value_num > rule_num * 2.5:
        return 0.0, {
            "penalty": max_penalty,
            "bonus": 0,
            "raw": 0,
            "max": weight,
            "kill_switch": True
        }

    # ----------------------------
    # GOOD ZONE
    # ----------------------------
    if metric_type == "min" and value_num >= rule_num:
        applied_bonus = bonus
    elif metric_type == "max" and value_num <= rule_num:
        applied_bonus = bonus

    # ----------------------------
    # VIOLATION ZONE (CONVEX)
    # ----------------------------
    else:
        if metric_type == "min":
            distance = rule_num - value_num
        else:
            distance = value_num - rule_num

        if distance <= soft:
            penalty = (distance / soft) ** 1.4 * max_penalty * slope
        elif distance <= hard:
            penalty = max_penalty * 0.85
        else:
            penalty = max_penalty

    raw_score = max(weight - penalty + applied_bonus, 0)

    # bonus cap: max +20% del peso
    raw_score = min(raw_score, weight * 1.2)

    return raw_score, {
        "penalty": round(penalty, 2),
        "bonus": applied_bonus,
        "raw": round(raw_score, 2),
        "max": weight
    }







# ---------------------------------------------------------
# Qualitative scoring
# ---------------------------------------------------------

def score_qualitative_metric(metric, value, desired_state, states, weight):
    """
    Qualitative scoring with ordered states.
    Desired_state is the MIN acceptable state.
    Better states receive full score.
    Worse states are penalized progressively.
    """

    if value is None or value == "" or desired_state in ("", "n.m.", None):
        return 0.0, {"reason": "missing"}

    if value not in states or desired_state not in states:
        return 0.0, {
            "reason": "unknown_state",
            "value": value,
            "desired": desired_state
        }

    value_idx = states.index(value)
    desired_idx = states.index(desired_state)

    # Direction:
    # default = higher index is better
    inverted_metrics = {"ShrOut"}
    inverted = metric in inverted_metrics

    if inverted:
        # lower index is better
        distance = value_idx - desired_idx
    else:
        distance = desired_idx - value_idx

    # --------------------------------------------------
    # SCORING LOGIC
    # --------------------------------------------------

    if distance <= 0:
        # equal or better than desired
        score = weight
    elif distance == 1:
        score = weight * 0.6
    elif distance == 2:
        score = weight * 0.35
    else:
        score = 0.0

    return score, {
        "value": value,
        "desired": desired_state,
        "distance": distance,
        "score": round(score, 2),
        "max": weight
    }



# ---------------------------------------------------------
# Normalization
# ---------------------------------------------------------

def normalize_score(raw, max_score):
    if max_score <= 0:
        return 0.0

    ratio = max(0, min(raw / max_score, 1))

    # curva a S leggera: severa sotto 50, premiante sopra 70
    adjusted = ratio ** 1.05

    return round(adjusted * 100, 1)



# ---------------------------------------------------------
# Helpers
# ---------------------------------------------------------

def parse_rule(rule: str):
    """
    Parses a rule-of-thumb string and returns:
    (operator, threshold, is_percentage)
    """
    rule = rule.strip().lower()

    if rule in ("n.m.", "", None):
        return None, None, None

    is_percentage = "%" in rule

    if rule.startswith("<"):
        op = "max"
        value = float(rule[1:].replace("%", ""))
    elif rule.startswith(">"):
        op = "min"
        value = float(rule[1:].replace("%", ""))
    else:
        # fallback: exact numeric threshold
        op = "min"
        value = float(rule.replace("%", ""))

    return op, value, is_percentage

