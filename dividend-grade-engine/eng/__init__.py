import pandas as pd
import json
from pathlib import Path

from eng.scoring import (
    score_quantitative_metric,
    score_qualitative_metric,
    normalize_score
)
from eng.explain import (
    explain_quantitative,
    explain_qualitative
)


class DividendGradeEngine:
    """
    Core engine for computing Dividend Safety score
    based on sector-aware rule of thumbs and weights.
    """

    def __init__(
        self,
        rules_path,
        weights_path,
        qualitative_states_path,
        penalties_path
    ):
        self.rules = pd.read_csv(rules_path)
        self.weights = pd.read_csv(weights_path)

        with open(qualitative_states_path, "r") as f:
            self.qual_states = json.load(f)

        with open(penalties_path, "r") as f:
            self.penalties = json.load(f)

        # Normalize text keys
        self.rules["Sub-sector"] = self.rules["Sub-sector"].fillna("")
        self.weights["Sub-sector"] = self.weights["Sub-sector"].fillna("")

    # ---------------------------------------------------------
    # Matching logic
    # ---------------------------------------------------------

    def _match_row(self, df, strct, gics, sub_sector):
        """
        Match most specific row:
        (Strct, GICS, Sub-sector) →
        fallback to sector default →
        fallback to structure default
        """
        candidates = df[
            (df["Strct"] == strct) &
            (df["GICS"] == gics) &
            (df["Sub-sector"] == sub_sector)
        ]

        if not candidates.empty:
            return candidates.iloc[0]

        candidates = df[
            (df["Strct"] == strct) &
            (df["GICS"] == gics) &
            (df["Sub-sector"] == "")
        ]

        if not candidates.empty:
            return candidates.iloc[0]

        candidates = df[
            (df["Strct"] == strct) &
            (df["GICS"] == "")
        ]

        if not candidates.empty:
            return candidates.iloc[0]

        raise ValueError(f"No matching rule found for {strct} / {gics} / {sub_sector}")

    # ---------------------------------------------------------
    # Main computation
    # ---------------------------------------------------------

    def compute_grade(self, input_df):
        results = []

        for _, row in input_df.iterrows():
            explanation_lines = []
            raw_score = 0
            max_score = 0

            strct = row["Strct"]
            gics = row["GICS"]
            sub_sector = row.get("Sub-sector", "")

            rule_row = self._match_row(self.rules, strct, gics, sub_sector)
            weight_row = self._match_row(self.weights, strct, gics, sub_sector)

            for metric in self._metrics():
                value = row.get(metric, None)
                rule = rule_row[metric]
                weight = weight_row[metric]

                if weight == 0 or pd.isna(rule) or rule == "n.m.":
                    continue

                max_score += weight

                # Quantitative metric
                if metric in self.penalties:
                    metric_score, detail = score_quantitative_metric(
                        metric=metric,
                        value=value,
                        rule=rule,
                        weight=weight,
                        penalty_cfg=self.penalties[metric]
                    )
                    explanation_lines.append(
                        explain_quantitative(metric, value, rule, weight, detail)
                    )

                # Qualitative metric
                else:
                    metric_score, detail = score_qualitative_metric(
                        metric=metric,
                        value=value,
                        desired_state=rule,
                        states=self.qual_states.get(metric, []),
                        weight=weight
                    )
                    explanation_lines.append(
                        explain_qualitative(metric, value, rule, weight, detail)
                    )

                raw_score += metric_score

            final_score = normalize_score(raw_score, max_score)

            results.append({
                "Dividend_Safety": round(final_score, 1),
                "Dividend_Safety_Explanation": "\n".join(explanation_lines)
            })

        return pd.concat([input_df, pd.DataFrame(results)], axis=1)

    # ---------------------------------------------------------
    # Helpers
    # ---------------------------------------------------------

    @staticmethod
    def _metrics():
        return [
            "CFPR", "FCFPR",
            "CFPS", "FCFPS",
            "CFg", "Salesg",
            "ShrOut", "TtSales",
            "ROE", "ROIC",
            "OpM", "FCFM",
            "NDtE", "NDtC",
            "IC"
        ]


# -------------------------------------------------------------
# Convenience runner
# -------------------------------------------------------------

def run_dividend_grade(
    input_csv,
    output_csv,
    rules_csv,
    weights_csv,
    qualitative_states_json,
    penalties_json
):
    engine = DividendGradeEngine(
        rules_path=rules_csv,
        weights_path=weights_csv,
        qualitative_states_path=qualitative_states_json,
        penalties_path=penalties_json
    )

    df = pd.read_csv(input_csv)
    result = engine.compute_grade(df)
    result.to_csv(output_csv, index=False)
