"""Data-quality checks for the silver layer.

Each check targets one risk listed in docs/TEST_STRATEGY.md. Checks run on every
chunk as it is written; the results are added up for the whole run. An "error"
check that fails stops the pipeline (non-zero exit code, so CI fails too); a
"warning" is reported but does not stop it.
"""

from datetime import datetime

import pandas as pd

from src.text_cleaning import has_content

ERROR = "error"
WARNING = "warning"

# The 11 products seen in every month of the narratives archive (March 2025 – July 2026).
# A product outside this list means CFPB added or renamed a category: stop and review.
KNOWN_PRODUCTS = {
    "Checking or savings account",
    "Credit card",
    "Credit reporting or other personal consumer reports",
    "Debt collection",
    "Debt or credit management",
    "Money transfer, virtual currency, or money service",
    "Mortgage",
    "Payday loan, title loan, personal loan, or advance loan",
    "Prepaid card",
    "Student loan",
    "Vehicle loan or lease",
}

MIN_WORDS = 3   # shorter narratives carry too little text to classify

CHECKS = [
    # (name, severity, function returning a boolean Series of FAILING rows)
    ("Complaint ID present", ERROR, lambda df: df["complaint_id"].isna()),
    ("Complaint ID unique", ERROR, lambda df: df["complaint_id"].duplicated(keep=False)),
    ("Date received present", ERROR, lambda df: df["date_received"].isna()),
    ("Date received not in the future", ERROR, lambda df: df["date_received"] > pd.Timestamp(datetime.now())),
    ("Product in known list", ERROR, lambda df: ~df["product"].isin(KNOWN_PRODUCTS)),
    ("Issue not blank", ERROR, lambda df: df["issue"].astype(str).str.strip() == ""),
    ("Narrative has real words", ERROR, lambda df: ~df["narrative_clean"].map(has_content)),
    ("Company not blank", WARNING, lambda df: df["company"].astype(str).str.strip() == ""),
    (f"Narrative at least {MIN_WORDS} words", WARNING, lambda df: df["word_count"] < MIN_WORDS),
]


def check_chunk(df: pd.DataFrame) -> dict:
    """Run every check on one chunk. Returns {check name: number of failing rows}."""
    if df.empty:
        return {name: 0 for name, _, _ in CHECKS}
    return {name: int(fn(df).sum()) for name, _, fn in CHECKS}


def summarise(chunk_results: list, total_rows: int) -> list:
    """Add up chunk results into one pass/fail line per check."""
    out = []
    for name, severity, _ in CHECKS:
        failing = sum(r.get(name, 0) for r in chunk_results)
        out.append({"check": name, "severity": severity, "passed": failing == 0,
                    "failing_rows": failing, "rows_checked": total_rows})
    return out
