"""Analyse repeated (template) complaint texts in the silver layer.

The silver report found thousands of narratives that appear word for word many
times. This script answers, before deciding how the gold layer handles them:
  * Which products and months do the repeated texts come from?
  * How big are the repeat groups (a few copies, or thousands)?
  * What do the most common repeated texts say?

Writes docs/template_report.md.

Usage:
    python -m src.analyse_templates
"""

import argparse
from pathlib import Path

import pandas as pd

from src.build_silver import TEMPLATE_MIN_REPEATS

LOAD_COLUMNS = ["complaint_id", "month", "product", "company", "text_hash", "word_count"]
TOP_N = 15
PREVIEW_CHARS = 220
GROUP_SIZES = [(1, 1, "1 (unique)"), (2, 4, "2–4"), (5, 9, "5–9"), (10, 99, "10–99"),
               (100, 999, "100–999"), (1000, 10**9, "1,000+")]


# ---------------------------------------------------------------- analysis

def analyse(df: pd.DataFrame, min_repeats: int = TEMPLATE_MIN_REPEATS) -> dict:
    """Template statistics from silver rows (needs the LOAD_COLUMNS)."""
    counts = df["text_hash"].map(df["text_hash"].value_counts())
    df = df.assign(copies=counts.astype(int), is_template=counts >= min_repeats)

    def share_table(by: str) -> pd.DataFrame:
        t = df.groupby(by).agg(rows=("is_template", "size"), template_rows=("is_template", "sum"))
        t["template_share"] = t["template_rows"] / t["rows"]
        return t

    group_sizes = df.drop_duplicates("text_hash")["copies"]
    size_rows = []
    for lo, hi, label in GROUP_SIZES:
        in_bucket = group_sizes[(group_sizes >= lo) & (group_sizes <= hi)]
        size_rows.append({"copies": label, "distinct_texts": int(len(in_bucket)), "complaints": int(in_bucket.sum())})

    templates = df[df["is_template"]]
    top = (templates.groupby("text_hash")
           .agg(copies=("copies", "first"), main_product=("product", lambda s: s.mode().iat[0]),
                products=("product", "nunique"), companies=("company", "nunique"),
                first_month=("month", "min"), last_month=("month", "max"), words=("word_count", "first"))
           .sort_values("copies", ascending=False)
           .head(TOP_N))

    return {
        "rows": int(len(df)),
        "distinct_texts": int(df["text_hash"].nunique()),
        "template_texts": int(templates["text_hash"].nunique()),
        "template_rows": int(len(templates)),
        "rows_if_one_copy_kept": int(len(df) - len(templates) + templates["text_hash"].nunique()),
        "by_product": share_table("product").sort_values("rows", ascending=False),
        "by_month": share_table("month").sort_index(),
        "group_sizes": pd.DataFrame(size_rows),
        "top": top,
    }


# ---------------------------------------------------------------- report

def _cell(text: str) -> str:
    """Make text safe for one Markdown table cell."""
    text = " ".join(str(text).split())
    if len(text) > PREVIEW_CHARS:
        text = text[:PREVIEW_CHARS].rstrip() + " …"
    return text.replace("|", "\\|")


def _pct(x: float) -> str:
    return f"{100 * x:.1f}%"


def render(r: dict, previews: dict, min_repeats: int = TEMPLATE_MIN_REPEATS) -> str:
    lines = [
        "# Template complaint analysis",
        "",
        f"A **template** is a narrative whose cleaned text appears {min_repeats} or more times word for word.",
        "",
        "## Overview",
        "",
        "| Measure | Value |",
        "| --- | --- |",
        f"| Complaints in silver | {r['rows']:,} |",
        f"| Distinct texts | {r['distinct_texts']:,} |",
        f"| Template texts | {r['template_texts']:,} |",
        f"| Complaints that use a template text | {r['template_rows']:,} ({_pct(r['template_rows'] / r['rows'])}) |",
        f"| Complaints left if one copy of each template is kept | {r['rows_if_one_copy_kept']:,} |",
        "",
        "## By product",
        "",
        "| Product | Complaints | Template complaints | Template share |",
        "| --- | --- | --- | --- |",
    ]
    for row in r["by_product"].itertuples():
        lines.append(f"| {_cell(row.Index)} | {int(row.rows):,} | {int(row.template_rows):,} | {_pct(row.template_share)} |")
    lines += ["", "## By month", "", "| Month | Complaints | Template complaints | Template share |", "| --- | --- | --- | --- |"]
    for row in r["by_month"].itertuples():
        lines.append(f"| {row.Index} | {int(row.rows):,} | {int(row.template_rows):,} | {_pct(row.template_share)} |")
    lines += ["", "## How many copies each text has", "", "| Copies of the same text | Distinct texts | Complaints |", "| --- | --- | --- |"]
    for row in r["group_sizes"].itertuples():
        lines.append(f"| {row.copies} | {int(row.distinct_texts):,} | {int(row.complaints):,} |")
    lines += [
        "",
        f"## Top {TOP_N} template texts",
        "",
        "| Copies | Main product | Products | Companies | First month | Last month | Words | Text (start) |",
        "| --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in r["top"].itertuples():
        lines.append(
            f"| {int(row.copies):,} | {_cell(row.main_product)} | {int(row.products)} | {int(row.companies)} | "
            f"{row.first_month} | {row.last_month} | {int(row.words)} | {_cell(previews.get(row.Index, ''))} |"
        )
    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------- loading

def latest_silver(silver_root: Path) -> Path:
    batches = sorted(d for d in silver_root.iterdir() if d.is_dir() and any(d.glob("part-*.parquet"))) if silver_root.exists() else []
    if not batches:
        raise SystemExit(f"No silver output in {silver_root}. Run `python -m src.build_silver` first.")
    return batches[-1]


def load_previews(silver_dir: Path, hashes: list) -> dict:
    """Read the text of only the given template fingerprints (one example each)."""
    if not hashes:
        return {}
    rows = pd.read_parquet(silver_dir, columns=["text_hash", "narrative_clean"], filters=[("text_hash", "in", list(hashes))])
    return rows.drop_duplicates("text_hash").set_index("text_hash")["narrative_clean"].to_dict()


def main():
    parser = argparse.ArgumentParser(description="Analyse repeated template texts in the silver layer.")
    parser.add_argument("--silver", type=Path, default=Path("data/silver/narratives"))
    parser.add_argument("--out", type=Path, default=Path("docs/template_report.md"))
    args = parser.parse_args()

    silver_dir = latest_silver(args.silver)
    print(f"Reading {silver_dir} ...")
    df = pd.read_parquet(silver_dir, columns=LOAD_COLUMNS)
    print(f"  {len(df):,} complaints loaded; analysing ...")
    result = analyse(df)
    previews = load_previews(silver_dir, result["top"].index.tolist())
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(render(result, previews), encoding="utf-8")
    print(f"Template complaints: {result['template_rows']:,} of {result['rows']:,}")
    print(f"Report written to {args.out}")


if __name__ == "__main__":
    main()
