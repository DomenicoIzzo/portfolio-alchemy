import pandas as pd
import json

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

    def __init__(self, rules_path, weights_path, qualitative_states_path, penalties_path):
        self.rules = pd.read_csv(rules_path, sep=";")
        self.weights = pd.read_csv(weights_path, sep=";")

        with open(qualitative_states_path) as f:
            self.qual_states = json.load(f)

        with open(penalties_path) as f:
            self.penalties = json.load(f)

        self.rules["Sub-sector"] = self.rules["Sub-sector"].fillna("")
        self.weights["Sub-sector"] = self.weights["Sub-sector"].fillna("")

    def _match_row(self, df, strct, gics, sub_sector):
        """
        Matching priority:
        1) Strct + GICS + Sub-sector
        2) Strct + GICS + General
        3) Strct + GICS + ""
        4) Strct + ""
        """

        # 1) full match
        mask = (
            (df["Strct"] == strct) &
            (df["GICS"] == gics) &
            (df["Sub-sector"] == sub_sector)
        )
        if not df[mask].empty:
            return df[mask].iloc[0]

        # 2) fallback to "General"
        mask = (
            (df["Strct"] == strct) &
            (df["GICS"] == gics) &
            (df["Sub-sector"] == "General")
        )
        if not df[mask].empty:
            return df[mask].iloc[0]

        # 3) empty Sub-sector
        mask = (
            (df["Strct"] == strct) &
            (df["GICS"] == gics) &
            (df["Sub-sector"] == "")
        )
        if not df[mask].empty:
            return df[mask].iloc[0]

        # 4) only structure
        mask = (df["Strct"] == strct)
        if not df[mask].empty:
            return df[mask].iloc[0]

        raise ValueError(
            f"No matching row for Strct={strct}, GICS={gics}, Sub-sector={sub_sector}"
        )

    def compute_grade(self, input_df):
        results = []

        for _, row in input_df.iterrows():
            explanation = []
            raw_score = 0.0
            max_score = 0.0

            strct = row["Strct"]
            gics = row["GICS"]
            sub_sector = row.get("Sub-sector", "")

            rule_row = self._match_row(self.rules, strct, gics, sub_sector)
            weight_row = self._match_row(self.weights, strct, gics, sub_sector)

            qualitative_bad = 0
            qualitative_total = 0

            for metric in self._metrics():
                rule = rule_row.get(metric)
                weight = weight_row.get(metric, 0)
                value = row.get(metric)

                if weight == 0 or rule in ("", "n.m.", None):
                    continue

                max_score += weight

                # -----------------------------
                # QUANTITATIVE
                # -----------------------------
                if metric in self.penalties:
                    score, detail = score_quantitative_metric(
                        metric=metric,
                        value=value,
                        rule=rule,
                        weight=weight,
                        penalty_cfg=self.penalties[metric]
                    )

                    raw_score += score

                    explanation.append(
                        f"[{metric}] value={value}, rule={rule}, "
                        f"penalty={detail.get('penalty', 0)}, "
                        f"bonus={detail.get('bonus', 0)}, "
                        f"score={score:.2f}/{weight}"
                    )

                # -----------------------------
                # QUALITATIVE
                # -----------------------------
                else:
                    qualitative_total += 1

                    score, detail = score_qualitative_metric(
                        metric=metric,
                        value=value,
                        desired_state=rule,
                        states=self.qual_states.get(metric, []),
                        weight=weight
                    )

                    if score < weight * 0.5:
                        qualitative_bad += 1

                    raw_score += score

                    explanation.append(
                        f"[{metric}] value='{value}', desired='{rule}', "
                        f"score={score:.2f}/{weight}"
                    )

            # -----------------------------
            # QUALITATIVE COHERENCE MALUS
            # -----------------------------
            if qualitative_total > 0:
                bad_ratio = qualitative_bad / qualitative_total
                if bad_ratio >= 0.5:
                    raw_score *= 0.7
                elif bad_ratio >= 0.3:
                    raw_score *= 0.85

            # -----------------------------
            # DIVIDEND SUSTAINABILITY GATE
            # -----------------------------
            try:
                cfpr = float(str(row.get("CFPR")).replace("%", "")) / 100
                fcfpr = float(str(row.get("FCFPR")).replace("%", "")) / 100
            except:
                cfpr = fcfpr = None

            if cfpr is not None and cfpr > 1.2:
                raw_score *= 0.4
            elif fcfpr is not None and fcfpr > 1.2:
                raw_score *= 0.6

            final_score = normalize_score(raw_score, max_score)

            results.append({
                "Dividend_Safety": round(final_score, 1),
                "Dividend_Safety_Explanation": "\n".join(explanation)
            })

        return pd.concat([input_df, pd.DataFrame(results)], axis=1)



    
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

        return pd.concat([input_df, pd.DataFrame(results)], axis=1)

