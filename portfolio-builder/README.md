
PortfolioAlchemy — Portfolio Construction Toolkit (example)
---------------------------------------------------------

This package contains:
- main.py : main script to run the portfolio construction
- config/filters.json : screening parameters (editable)
- config/weights.csv : factor weights used to aggregate the 1-100 score (editable)
- config/qualitative_states.json : qualitative mappings used in scoring
- Tickers.xlsx : input data file (copied from the uploaded file)
- Tickers_with_Weights.xlsx : output with Weight%, WeightQ, Weight$ columns

Run the tool:
    python main.py

The tool is intentionally flexible: edit config files to change screening, factor weights,
and qualitative mappings. The scoring logic uses normalized metrics across candidates and
then applies the configured factor weights to compute a 0-100 score.
