"""Silver layer: cleaned, typed, deduplicated complaints with narratives.

Reads the latest narratives batch from bronze and, chunk by chunk:
  1. keeps only complaints that have a written narrative
  2. standardises column names and types (dates, IDs, yes/no flags)
  3. cleans the narrative text (placeholders for redactions, tidy whitespace)
  4. removes duplicate complaint IDs and texts that are only placeholders
  5. adds month, word count and a text fingerprint (to spot template complaints)
  6. runs data-quality checks on every chunk
  7. writes Parquet files to data/silver/narratives/<batch>/

The full narrative set is kept here. Capping credit reporting and splitting
into train/validation/test happen later, in the gold layer.

Usage:
    python -m src.build_silver
    python -m src.build_silver --batch data/bronze/narratives/2026-11-06
"""

import argparse
import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from src.columns import standardise_columns
from src.profile_raw import data_files, iter_chunks, latest_batch
from src.silver_checks import ERROR, check_chunk, summarise
from src.text_cleaning import clean_narrative, has_content, text_hash, word_count

SILVER_COLUMNS = [
    "complaint_id", "date_received", "month", "product", "sub_product", "issue", "sub_issue",
    "company", "state", "submitted_via", "company_response_to_consumer", "timely_response",
    "narrative", "narrative_clean", "word_count", "text_hash", "source_file",
]
TEXT_COLUMNS = [
    "product", "sub_product", "issue", "sub_issue", "company", "state",
    "submitted_via", "company_response_to_consumer",
]
TEMPLATE_MIN_REPEATS = 5   # the same text this many times or more counts as a template


def transform_chunk(chunk: pd.DataFrame, source: str) -> tuple[pd.DataFrame, Counter]:
    """Clean one bronze chunk. Returns (silver rows, counts of rows dropped by reason)."""
    dropped = Counter()
    df = chunk.rename(columns=standardise_columns(chunk.columns)).reset_index(drop=True)
    for col in SILVER_COLUMNS:
        if col not in df and col not in {"month", "narrative_clean", "word_count", "text_hash", "source_file"}:
            df[col] = ""

    has_narrative = (df["narrative"].astype(str).str.strip() != "").astype(bool)
    dropped["no narrative"] += int((~has_narrative).sum())
    df = df[has_narrative].copy()
    if df.empty:
        # Many 2026 chunks have no narratives at all; nothing to clean.
        return pd.DataFrame(columns=SILVER_COLUMNS), dropped

    df["narrative_clean"] = df["narrative"].map(clean_narrative).astype(str)
    content = df["narrative_clean"].map(has_content).astype(bool)
    dropped["only redaction placeholders"] += int((~content).sum())
    df = df[content].copy()
    if df.empty:
        return pd.DataFrame(columns=SILVER_COLUMNS), dropped

    df["complaint_id"] = pd.to_numeric(df["complaint_id"], errors="coerce").astype("Int64")
    df["date_received"] = pd.to_datetime(df["date_received"], errors="coerce", format="mixed")
    bad = (df["complaint_id"].isna() | df["date_received"].isna()).astype(bool)
    dropped["unreadable ID or date"] += int(bad.sum())
    df = df[~bad].copy()
    if df.empty:
        return pd.DataFrame(columns=SILVER_COLUMNS), dropped

    df["month"] = df["date_received"].dt.strftime("%Y-%m")
    for col in TEXT_COLUMNS:
        df[col] = df[col].astype(str).str.strip()
    df["timely_response"] = df["timely_response"].astype(str).str.strip().str.lower().map({"yes": True, "no": False}).astype("boolean")
    df["word_count"] = df["narrative_clean"].map(word_count).astype("int32")
    df["text_hash"] = df["narrative_clean"].map(text_hash)
    df["source_file"] = source
    return df[SILVER_COLUMNS].reset_index(drop=True), dropped


def write_part(df: pd.DataFrame, path: Path) -> None:
    """Write one silver part file (kept separate so tests can swap the format)."""
    df.to_parquet(path, index=False)


def build(batch: Path, silver_root: Path, report_path: Path) -> dict:
    """Build silver from one bronze batch. Returns the run summary."""
    out_dir = silver_root / batch.name
    out_dir.mkdir(parents=True, exist_ok=True)
    for old in out_dir.glob("part-*"):
        old.unlink()   # a rebuild replaces the previous output

    seen_ids: set = set()
    hash_counts: Counter = Counter()
    dropped: Counter = Counter()
    chunk_results = []
    rows_in = rows_out = 0
    part = 0

    for path in data_files(batch):
        print(f"Reading {path.name} ...")
        for source, chunk in iter_chunks(path):
            rows_in += len(chunk)
            df, chunk_dropped = transform_chunk(chunk, source)
            dropped.update(chunk_dropped)

            if df.empty:
                print(f"  {rows_in:,} rows read, {rows_out:,} kept (no narratives in this chunk)")
                continue
            duplicate = (df["complaint_id"].isin(seen_ids) | df["complaint_id"].duplicated()).astype(bool)
            dropped["duplicate complaint ID"] += int(duplicate.sum())
            df = df[~duplicate]
            seen_ids.update(df["complaint_id"].tolist())

            chunk_results.append(check_chunk(df))
            hash_counts.update(df["text_hash"].tolist())
            if len(df):
                part += 1
                write_part(df, out_dir / f"part-{part:05d}.parquet")
                rows_out += len(df)
            print(f"  {rows_in:,} rows read, {rows_out:,} kept")

    repeated = {h: n for h, n in hash_counts.items() if n >= TEMPLATE_MIN_REPEATS}
    summary = {
        "batch": batch.as_posix(),
        "built_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "rows_read": rows_in,
        "rows_written": rows_out,
        "rows_dropped": dict(dropped),
        "part_files": part,
        "template_texts": len(repeated),
        "rows_with_template_text": sum(repeated.values()),
        "checks": summarise(chunk_results, rows_out),
    }
    (out_dir / "_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(render_report(summary), encoding="utf-8")
    return summary


def render_report(s: dict) -> str:
    lines = [
        "# Silver layer report",
        "",
        f"Bronze batch: `{s['batch']}` · built {s['built_at_utc']}",
        "",
        "## Rows",
        "",
        "| Step | Rows |",
        "| --- | --- |",
        f"| Read from bronze | {s['rows_read']:,} |",
    ]
    lines += [f"| Dropped: {reason} | {n:,} |" for reason, n in sorted(s["rows_dropped"].items())]
    lines += [
        f"| **Written to silver** | **{s['rows_written']:,}** |",
        "",
        "## Repeated (template) texts",
        "",
        f"{s['template_texts']:,} distinct texts appear {TEMPLATE_MIN_REPEATS} or more times, "
        f"covering {s['rows_with_template_text']:,} complaints. They are kept in silver and flagged by "
        "`text_hash`; the gold layer decides whether to remove them.",
        "",
        "## Data-quality checks",
        "",
        "| Check | Severity | Result | Failing rows |",
        "| --- | --- | --- | --- |",
    ]
    for c in s["checks"]:
        lines.append(f"| {c['check']} | {c['severity']} | {'Pass' if c['passed'] else 'FAIL'} | {c['failing_rows']:,} |")
    return "\n".join(lines) + "\n"


def main():
    parser = argparse.ArgumentParser(description="Build the silver layer from a bronze narratives batch.")
    parser.add_argument("--batch", type=Path, help="Bronze batch folder (default: latest narratives batch)")
    parser.add_argument("--bronze", type=Path, default=Path("data/bronze"))
    parser.add_argument("--silver", type=Path, default=Path("data/silver/narratives"))
    parser.add_argument("--report", type=Path, default=Path("docs/silver_report.md"))
    args = parser.parse_args()

    batch = args.batch or latest_batch(args.bronze / "narratives")
    summary = build(batch, args.silver, args.report)
    failed = [c for c in summary["checks"] if c["severity"] == ERROR and not c["passed"]]
    print(f"Silver rows written: {summary['rows_written']:,}")
    print(f"Report written to {args.report}")
    if failed:
        print("FAILED checks: " + ", ".join(c["check"] for c in failed))
        sys.exit(1)
    print("All error-level checks passed.")


if __name__ == "__main__":
    main()
