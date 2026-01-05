import pandas as pd
from pathlib import Path

from eng.dividend_grade import DividendGradeEngine

# --------------------------------------------------
# PATH SETUP
# --------------------------------------------------

BASE_DIR = Path(__file__).resolve().parent

CFG_DIR = BASE_DIR / "cfg"
IO_DIR = BASE_DIR / "io"

INPUT_FILE = IO_DIR / "sample_input.csv"
OUTPUT_FILE = IO_DIR / "output_with_dividend_grade.csv"

# --------------------------------------------------
# ENGINE INITIALIZATION
# --------------------------------------------------

engine = DividendGradeEngine(
    rules_path=CFG_DIR / "rule_of_thumbs.csv",
    weights_path=CFG_DIR / "weights.csv",
    qualitative_states_path=CFG_DIR / "qualitative_states.json",
    penalties_path=CFG_DIR / "penalties.json",
)

# --------------------------------------------------
# RUN ENGINE
# --------------------------------------------------

df = pd.read_csv(INPUT_FILE)

result_df = engine.compute_grade(df)

result_df.to_csv(OUTPUT_FILE, index=False)

print("✅ Dividend Safety computation completed")
print(f"📄 Output written to: {OUTPUT_FILE}")
