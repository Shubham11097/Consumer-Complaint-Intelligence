"""Gold layer: model-ready datasets and analytics tables.

Built from the latest silver output in two passes, so the full text never has
to fit in memory at once.

Pass 1 (metadata only) decides which complaints go into the model data:
  1. keep ONE copy of every exact text (the earliest), so the same letter can
     never appear in both training and test data (leakage)
  2. drop narratives shorter than MIN_WORDS
  3. split by time: train / validation / test
  4. cap credit reporting in the TRAINING split only, sampled evenly across
     months, so the model is not dominated by one product. Validation and test
     keep their natural mix, so scores reflect real conditions.

Pass 2 reads the silver files one at a time and writes the selected rows to
  data/gold/<silver batch>/model/{train,validation,test}/part-*.parquet

Analytics tables (all silver complaints, templates included) go to
  data/gold/<silver batch>/analytics/*.parquet and *.csv  (for SQL / Power BI)

Usage:
    python -m src.build_gold
    python -m src.build_gold --credit-reporting-cap 50000
"""

import argparse
import json
import math
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from src.analyse_templates import latest_silver
from src.build_silver import TEMPLATE_MIN_REPEATS
from src.silver_checks import KNOWN_PRODUCTS

CREDIT_REPORTING = "Credit reporting or other personal consumer reports"
DEFAULT_CAP = 50_000
MIN_WORDS = 3
SEED = 42

# Time-based split (inclusive month ranges).
SPLITS = {
    "train": ("2022-11", "2026-02"),
    "validation": ("2026-03", "2026-04"),
    "test": ("2026-05", "2026-07"),
}
SPLIT_ORDER = list(SPLITS)

META_COLUMNS = ["complaint_id", "date_received", "month", "product", "issue", "company", "word_count", "text_hash"]
TEXT_COLUMNS = ["complaint_id", "narrative_clean"]
GOLD_COLUMNS = ["complaint_id", "date_received", "month", "split", "product", "issue", "company",
                "narrative_clean", "word_count", "text_hash", "copies", "is_template"]

ERROR = "error"


# ---------------------------------------------------------------- pass 1: selection

def split_for_month(month: str):
    """Which split a month belongs to, or None if outside every range."""
    for name, (start, end) in SPLITS.items():
        if start <= month <= end:
            return name
    return None


def cap_evenly_by_month(df: pd.DataFrame, cap: int, seed: int = SEED) -> pd.DataFrame:
    """Sample at most `cap` rows, spread as evenly as possible across months."""
    if len(df) <= cap:
        return df
    months = df["month"].nunique()
    quota = math.ceil(cap / months)
    # Shuffle once, then take up to `quota` rows from each month.
    sampled = df.sample(frac=1, random_state=seed).groupby("month").head(quota)
    if len(sampled) > cap:
        sampled = sampled.sample(n=cap, random_state=seed)
    return sampled


def select(meta: pd.DataFrame, cap: int = DEFAULT_CAP, seed: int = SEED) -> tuple[pd.DataFrame, dict]:
    """Choose model rows from silver metadata. Returns (selection, step counts)."""
    steps = {"silver complaints": len(meta)}
    copies = meta["text_hash"].map(meta["text_hash"].value_counts())
    df = meta.assign(copies=copies.astype(int))

    df = (df.sort_values(["date_received", "complaint_id"])
            .drop_duplicates("text_hash", keep="first"))
    steps["after keeping one copy of each text"] = len(df)

    df = df[df["word_count"] >= MIN_WORDS]
    steps[f"after dropping narratives under {MIN_WORDS} words"] = len(df)

    df = df.assign(split=df["month"].map(split_for_month))
    outside = int(df["split"].isna().sum())
    df = df[df["split"].notna()]
    steps["outside every split (dropped)"] = outside

    is_train_cr = (df["split"] == "train") & (df["product"] == CREDIT_REPORTING)
    capped = cap_evenly_by_month(df[is_train_cr], cap, seed)
    steps["credit reporting in train before cap"] = int(is_train_cr.sum())
    df = pd.concat([df[~is_train_cr], capped])
    steps["credit reporting in train after cap"] = len(capped)
    steps["model complaints"] = len(df)

    df = df.assign(is_template=df["copies"] >= TEMPLATE_MIN_REPEATS)
    return df.sort_values(["date_received", "complaint_id"]).reset_index(drop=True), steps


def check_gold(sel: pd.DataFrame, cap: int) -> list:
    """Error-level checks on the selection; any failure stops the build."""
    results = []

    def add(name, failing, detail=""):
        results.append({"check": name, "severity": ERROR, "passed": failing == 0, "failing": int(failing), "detail": detail})

    splits_per_id = sel.groupby("complaint_id")["split"].nunique()
    add("Each complaint in exactly one split", (splits_per_id > 1).sum())
    splits_per_text = sel.groupby("text_hash")["split"].nunique()
    add("No text shared between splits (no leakage)", (splits_per_text > 1).sum())
    missing = [s for s in SPLIT_ORDER if not (sel["split"] == s).any()]
    add("Every split has data", len(missing), ", ".join(missing))
    train_products = set(sel.loc[sel["split"] == "train", "product"])
    absent = sorted(KNOWN_PRODUCTS - train_products)
    add("All 11 products present in train", len(absent), ", ".join(absent))
    order_bad = 0
    for earlier, later in zip(SPLIT_ORDER, SPLIT_ORDER[1:]):
        a, b = sel.loc[sel["split"] == earlier, "month"], sel.loc[sel["split"] == later, "month"]
        if len(a) and len(b) and a.max() >= b.min():
            order_bad += 1
    add("Splits are in time order (train < validation < test)", order_bad)
    train_cr = int(((sel["split"] == "train") & (sel["product"] == CREDIT_REPORTING)).sum())
    add(f"Credit reporting in train at most {cap:,}", max(0, train_cr - cap))
    add(f"No narrative under {MIN_WORDS} words", (sel["word_count"] < MIN_WORDS).sum())
    return results


# ---------------------------------------------------------------- analytics tables

def analytics_tables(meta: pd.DataFrame) -> dict:
    """Monthly counts over ALL silver complaints (templates included), for SQL / Power BI."""
    copies = meta["text_hash"].map(meta["text_hash"].value_counts())
    df = meta.assign(is_template=(copies >= TEMPLATE_MIN_REPEATS).astype(int))

    def monthly(keys):
        return (df.groupby(keys).agg(complaints=("complaint_id", "size"), template_complaints=("is_template", "sum"))
                  .reset_index().sort_values(keys).reset_index(drop=True))

    return {
        "monthly_product_issue": monthly(["month", "product", "issue"]),
        "monthly_company_product": monthly(["month", "company", "product"]),
    }


# ---------------------------------------------------------------- pass 2: writing

def read_meta(silver_dir: Path) -> pd.DataFrame:
    return pd.read_parquet(silver_dir, columns=META_COLUMNS)


def read_part(path: Path) -> pd.DataFrame:
    return pd.read_parquet(path, columns=TEXT_COLUMNS)


def write_part(df: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(path, index=False)


def write_table(df: pd.DataFrame, path_stem: Path) -> None:
    path_stem.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(path_stem.with_suffix(".parquet"), index=False)
    df.to_csv(path_stem.with_suffix(".csv"), index=False)


def write_model_data(silver_dir: Path, sel: pd.DataFrame, model_dir: Path) -> dict:
    """Join selected rows to their text, one silver part at a time. Returns rows written per split."""
    for old in model_dir.glob("*/part-*.parquet"):
        old.unlink()   # a rebuild replaces the previous output
    keep = sel.drop(columns=[c for c in sel.columns if c not in GOLD_COLUMNS])
    written = {s: 0 for s in SPLIT_ORDER}
    for i, part in enumerate(sorted(silver_dir.glob("part-*.parquet")), start=1):
        text = read_part(part)
        rows = keep.merge(text, on="complaint_id", how="inner")
        for split, group in rows.groupby("split"):
            write_part(group[GOLD_COLUMNS].reset_index(drop=True), model_dir / split / f"part-{i:05d}.parquet")
            written[split] += len(group)
        print(f"  {part.name}: {sum(written.values()):,} model rows written so far")
    return written


# ---------------------------------------------------------------- report

def render_report(summary: dict, sel: pd.DataFrame) -> str:
    lines = [
        "# Gold layer report",
        "",
        f"Silver: `{summary['silver']}` · built {summary['built_at_utc']}",
        "",
        "## Model data: how rows were selected",
        "",
        "| Step | Complaints |",
        "| --- | --- |",
        *[f"| {k} | {v:,} |" for k, v in summary["steps"].items()],
        "",
        "## Splits",
        "",
        "| Split | Months | Complaints | Template share |",
        "| --- | --- | --- | --- |",
    ]
    for s in SPLIT_ORDER:
        part = sel[sel["split"] == s]
        share = f"{100 * part['is_template'].mean():.1f}%" if len(part) else "n/a"
        lines.append(f"| {s} | {SPLITS[s][0]} – {SPLITS[s][1]} | {len(part):,} | {share} |")
    counts = sel.groupby(["product", "split"]).size().unstack(fill_value=0).reindex(columns=SPLIT_ORDER, fill_value=0)
    counts = counts.sort_values("train", ascending=False)
    lines += ["", "## Products per split", "", "| Product | " + " | ".join(SPLIT_ORDER) + " |",
              "| --- | " + " | ".join("---" for _ in SPLIT_ORDER) + " |"]
    for product, row in counts.iterrows():
        lines.append(f"| {product} | " + " | ".join(f"{int(row[s]):,}" for s in SPLIT_ORDER) + " |")
    lines += ["", "## Checks", "", "| Check | Result | Failing | Detail |", "| --- | --- | --- | --- |"]
    for c in summary["checks"]:
        lines.append(f"| {c['check']} | {'Pass' if c['passed'] else 'FAIL'} | {c['failing']:,} | {c['detail']} |")
    lines += ["", "## Analytics tables", "", "| Table | Rows |", "| --- | --- |"]
    lines += [f"| {name} | {n:,} |" for name, n in summary["analytics_rows"].items()]
    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------- main

def build(silver_dir: Path, gold_root: Path, report_path: Path, cap: int = DEFAULT_CAP) -> dict:
    out = gold_root / silver_dir.name
    print(f"Reading silver metadata from {silver_dir} ...")
    meta = read_meta(silver_dir)

    print("Selecting model rows ...")
    sel, steps = select(meta, cap)
    checks = check_gold(sel, cap)

    print("Writing analytics tables ...")
    tables = analytics_tables(meta)
    for name, table in tables.items():
        write_table(table, out / "analytics" / name)

    summary = {
        "silver": silver_dir.as_posix(),
        "built_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "credit_reporting_cap": cap,
        "splits": SPLITS,
        "steps": steps,
        "checks": checks,
        "analytics_rows": {name: len(t) for name, t in tables.items()},
    }
    if all(c["passed"] for c in checks):
        print("Writing model data ...")
        summary["rows_written"] = write_model_data(silver_dir, sel, out / "model")
    else:
        summary["rows_written"] = {}
        print("Checks failed: model data not written.")

    out.mkdir(parents=True, exist_ok=True)
    (out / "_summary.json").write_text(json.dumps(summary, indent=2, default=str), encoding="utf-8")
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(render_report(summary, sel), encoding="utf-8")
    return summary


def main():
    parser = argparse.ArgumentParser(description="Build the gold layer from the latest silver output.")
    parser.add_argument("--silver", type=Path, default=Path("data/silver/narratives"))
    parser.add_argument("--gold", type=Path, default=Path("data/gold"))
    parser.add_argument("--report", type=Path, default=Path("docs/gold_report.md"))
    parser.add_argument("--credit-reporting-cap", type=int, default=DEFAULT_CAP)
    args = parser.parse_args()

    summary = build(latest_silver(args.silver), args.gold, args.report, args.credit_reporting_cap)
    print(f"Report written to {args.report}")
    failed = [c["check"] for c in summary["checks"] if not c["passed"]]
    if failed:
        print("FAILED checks: " + ", ".join(failed))
        sys.exit(1)
    print("Rows written: " + ", ".join(f"{s} {n:,}" for s, n in summary["rows_written"].items()))
    print("All checks passed.")


if __name__ == "__main__":
    main()
