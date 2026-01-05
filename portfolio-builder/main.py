
#!/usr/bin/env python3
import json, math
import pandas as pd
import numpy as np
from pathlib import Path

BASE = Path(__file__).resolve().parent
CONFIG = BASE / "config"
INPUT = BASE / "Tickers.xlsx"
OUTPUT = BASE / "Tickers_with_Weights.xlsx"

def load_configs():
    with open(CONFIG / "filters.json") as f:
        filters = json.load(f)
    weights = pd.read_csv(CONFIG / "weights.csv")
    with open(CONFIG / "qualitative_states.json") as f:
        qual = json.load(f)
    return filters, weights, qual

def normalize_series(s, higher_is_better=True):
    s = pd.to_numeric(s, errors='coerce')
    mn = s.min(skipna=True)
    mx = s.max(skipna=True)
    if pd.isna(mn) or pd.isna(mx) or mn == mx:
        out = pd.Series(0.5, index=s.index)
        out[s.isna()] = 0.0
        return out
    if higher_is_better:
        return (s - mn) / (mx - mn)
    else:
        return (mx - s) / (mx - mn)

def compute_score(df, weights_df, qual_map):
    scores = pd.DataFrame(index=df.index)
    scores['pct_from_expected_price'] = normalize_series(df.get('% From Expected Price'), higher_is_better=False).fillna(0)
    scores['pct_above_5y_avg_yield'] = normalize_series(df.get('% Above 5-Year Average Dividend Yield'), higher_is_better=True).fillna(0)
    pe = pd.to_numeric(df.get('P/E Ratio'), errors='coerce')
    pe5 = pd.to_numeric(df.get('5-Year Average P/E Ratio'), errors='coerce')
    ratio = pe / pe5.replace({0:np.nan})
    scores['pe_vs_5y_avg'] = normalize_series(ratio, higher_is_better=False).fillna(0)
    scores['div_growth_latest'] = normalize_series(df.get('Dividend Growth (Latest)'), higher_is_better=True).fillna(0)
    scores['div_growth_5y'] = normalize_series(df.get('5-Year Dividend Growth'), higher_is_better=True).fillna(0)
    scores['div_growth_10y'] = normalize_series(df.get('10-Year Dividend Growth'), higher_is_better=True).fillna(0)
    scores['div_growth_streak_years'] = normalize_series(df.get('Dividend Growth Streak (Years)'), higher_is_better=True).fillna(0)
    scores['uninterrupted_dividend_streak_years'] = normalize_series(df.get('Uninterrupted Dividend Streak (Years)'), higher_is_better=True).fillna(0)
    recession_map = qual_map.get('RecessionDividend_order', {"Increased":3,"Maintained":2,"Cut":1})
    rec_values = df.get('Recession Dividend').map(lambda x: recession_map.get(str(x).strip(), np.nan))
    scores['recession_dividend'] = normalize_series(rec_values, higher_is_better=True).fillna(0)
    scores['recession_return'] = normalize_series(df.get('Recession Return'), higher_is_better=True).fillna(0)

    weights = weights_df.set_index('factor_code')['weight'].to_dict()
    total = 0.0
    weighted = pd.Series(0.0, index=df.index)
    for factor, w in weights.items():
        if factor not in scores.columns:
            continue
        weighted += scores[factor] * float(w)
        total += float(w)
    if total == 0:
        total = 1.0
    final_score = (weighted / total) * 100.0
    return final_score.clip(1,100)

def screen_universe(df, filters):
    ok = pd.Series(True, index=df.index)
    if filters.get('allowed_Strct'):
        ok &= df['Strct'].isin(filters['allowed_Strct'])
    if filters.get('allowed_GICS'):
        ok &= df['GICS'].isin(filters['allowed_GICS'])
    if filters.get('min_Dividend_Grade') is not None:
        ok &= pd.to_numeric(df.get('Dividend Grade'), errors='coerce').fillna(0) >= float(filters['min_Dividend_Grade'])
    dy = pd.to_numeric(df.get('Dividend Yield'), errors='coerce')
    dy_low, dy_high = filters.get('Dividend_Yield_range', [0,100])
    ok &= dy.between(dy_low, dy_high, inclusive='both')
    if filters.get('min_Price') is not None:
        ok &= pd.to_numeric(df.get('Price'), errors='coerce').fillna(0) >= float(filters['min_Price'])
    if filters.get('min_Market_Cap_Millions') is not None:
        ok &= pd.to_numeric(df.get('Market Cap (Millions)'), errors='coerce').fillna(0) >= float(filters['min_Market_Cap_Millions'])
    if filters.get('allowed_Payment_Frequency'):
        ok &= df['Payment Frequency'].str.lower().isin([x.lower() for x in filters['allowed_Payment_Frequency']])
    if filters.get('allowed_Valuation'):
        ok &= df['Valuation'].isin(filters['allowed_Valuation'])
    return df[ok].copy()

def enforce_constraints(selected_df, investment_amount, max_n_tickers, max_gics_pct, max_income_pct):
    df = selected_df.copy()
    df = df.sort_values('Score', ascending=False).head(max_n_tickers).copy()
    df['raw_weight'] = df['Score'] / df['Score'].sum()
    df['weight_dollar'] = df['raw_weight'] * investment_amount
    max_gics_frac = max_gics_pct / 100.0
    max_income_frac = max_income_pct / 100.0

    def compute_incomes(local_df):
        dy = pd.to_numeric(local_df.get('Dividend Yield'), errors='coerce').fillna(0) / 100.0
        incomes = local_df['weight_dollar'] * dy
        return incomes.fillna(0)

    for iteration in range(30):
        incomes = compute_incomes(df)
        total_income = incomes.sum()
        # GICS cap
        gics_sums = df.groupby('GICS')['weight_dollar'].sum()
        gics_violations = gics_sums[gics_sums > (max_gics_frac * investment_amount)]
        if not gics_violations.empty:
            for gics, gval in gics_violations.items():
                allowed = max_gics_frac * investment_amount
                excess = gval - allowed
                mask = df['GICS'] == gics
                weights_in_gics = df.loc[mask, 'weight_dollar']
                if weights_in_gics.sum() <= 0:
                    continue
                reduction_ratio = allowed / weights_in_gics.sum()
                df.loc[mask, 'weight_dollar'] = df.loc[mask, 'weight_dollar'] * reduction_ratio
                others_mask = ~mask
                total_score_others = df.loc[others_mask, 'Score'].sum()
                if total_score_others > 0:
                    df.loc[others_mask, 'weight_dollar'] += (df.loc[others_mask, 'Score'] / total_score_others) * excess
        incomes = compute_incomes(df)
        total_income = incomes.sum()
        if total_income <= 0:
            break
        income_shares = incomes / total_income
        violators = income_shares > max_income_frac
        if violators.any():
            violator_idxs = df[violators].index.tolist()
            for idx in violator_idxs:
                allowed_income = max_income_frac * total_income
                dy = (pd.to_numeric(df.at[idx, 'Dividend Yield'], errors='coerce') or 0) / 100.0
                if dy <= 0:
                    continue
                allowed_weight_dollar = allowed_income / dy
                if allowed_weight_dollar < df.at[idx, 'weight_dollar']:
                    freed = df.at[idx, 'weight_dollar'] - allowed_weight_dollar
                    df.at[idx, 'weight_dollar'] = allowed_weight_dollar
                    others = df.index.difference([idx])
                    total_score_others = df.loc[others, 'Score'].sum()
                    if total_score_others > 0:
                        df.loc[others, 'weight_dollar'] += (df.loc[others, 'Score'] / total_score_others) * freed
            continue
        break

    df['Weight$'] = df['weight_dollar'].round(2)
    df['Weight%'] = (df['Weight$'] / investment_amount) * 100.0
    prices = pd.to_numeric(df.get('Price'), errors='coerce').fillna(0)
    df['WeightQ'] = (df['Weight$'] / prices).fillna(0).apply(lambda x: int(math.floor(x)) if x>0 else 0)
    df['Weight$_from_Q'] = df['WeightQ'] * prices
    df['Weight$_final'] = df['Weight$_from_Q']
    df = df.sort_values('Score', ascending=False)
    return df

def main():
    filters, weights_df, qual_map = load_configs()
    df = pd.read_excel(INPUT)
    original_len = len(df)
    screened = screen_universe(df, filters)
    screened_len = len(screened)
    score = compute_score(screened, weights_df, qual_map)
    screened['Score'] = score
    investment_amount = 50000.0
    max_n_tickers = 30
    max_gics_pct = 25.0
    max_income_pct = 5.0
    selected = enforce_constraints(screened, investment_amount, max_n_tickers, max_gics_pct, max_income_pct)
    out = df.merge(selected[['Score','Weight%','WeightQ','Weight$','Weight$_final']], left_on='Ticker', right_index=True, how='left')
    out['Weight%'] = out['Weight%'].fillna(0)
    out['WeightQ'] = out['WeightQ'].fillna(0).astype(int)
    out['Weight$'] = out['Weight$'].fillna(0)
    out.to_excel(OUTPUT, index=False)
    print(f"Processed {original_len} tickers, {screened_len} passed screening, {len(selected)} selected for allocation.")
    print(f"Output written to: {OUTPUT}")

if __name__ == "__main__":
    main()
