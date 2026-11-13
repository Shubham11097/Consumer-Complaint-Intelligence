"""Profile the raw bronze data to answer the week-1 questions.

  1. How many complaints are there, and how many have a written narrative?
  2. Which date range has stable product categories?
  3. Which products and issues are large enough to model?
  4. Are there duplicate complaint IDs or missing required columns?

Reads every .zip/.csv/.json file in a bronze batch folder in chunks (so large
files don't fill memory) and writes a Markdown report to docs/data_profile.md.

Usage:
    python -m src.profile_raw --source narratives      # latest narratives batch
    python -m src.profile_raw --source live            # latest live-database batch
    python -m src.profile_raw --batch data/bronze/narratives/2026-11-06
"""

import argparse
import io
import json
import zipfile
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np
import pandas as pd

from src.columns import missing_columns, standardise_columns

CHUNK_ROWS = 200_000
LENGTH_BUCKETS = [(0, 49), (50, 99), (100, 199), (200, 499), (500, 999), (1000, 10**9)]


# ---------------------------------------------------------------- reading

def _chunks_from_handle(handle, name: str):
    """Yield DataFrame chunks from one CSV or JSON file handle."""
    lower = name.lower()
    if lower.endswith(".csv"):
        yield from pd.read_csv(handle, dtype=str, chunksize=CHUNK_ROWS, keep_default_na=False)
    elif lower.endswith(".json"):
        raw = handle.read()
        text = raw.decode("utf-8") if isinstance(raw, bytes) else raw
        try:
            frame = pd.read_json(io.StringIO(text), dtype=False)
        except ValueError:
            frame = pd.read_json(io.StringIO(text), lines=True, dtype=False)
        # API-style exports nest each record under "_source".
        if "_source" in frame.columns:
            frame = pd.json_normalize(frame["_source"].tolist())
        yield frame.astype(str).replace({"None": "", "nan": ""})


def iter_chunks(path: Path):
    """Yield (source_name, DataFrame chunk) for a bronze file, including files inside a ZIP."""
    if path.suffix.lower() == ".zip":
        with zipfile.ZipFile(path) as archive:
            for member in archive.namelist():
                if member.lower().endswith((".csv", ".json")):
                    with archive.open(member) as handle:
                        for chunk in _chunks_from_handle(handle, member):
                            yield f"{path.name}/{member}", chunk
    else:
        with open(path, "rb") as handle:
            for chunk in _chunks_from_handle(handle, path.name):
                yield path.name, chunk


# ---------------------------------------------------------------- profiling

class Profile:
    """Running totals, updated chunk by chunk."""

    def __init__(self):
        self.rows = 0
        self.with_narrative = 0
        self.sources = Counter()
        self.columns_seen = {}
        self.missing_required = set()
        self.blank_counts = Counter()
        self.id_arrays = []
        self.non_numeric_ids = 0
        self.min_date = None
        self.max_date = None
        self.bad_dates = 0
        self.by_year = Counter()
        self.by_year_narr = Counter()
        self.product_year = defaultdict(Counter)      # product -> {year: narrative count}
        self.issue_counts = Counter()                 # (product, issue) -> narrative count
        self.length_buckets = Counter()

    def update(self, source: str, chunk: pd.DataFrame):
        mapping = standardise_columns(chunk.columns)
        self.columns_seen.update(mapping)
        self.missing_required.update(missing_columns(chunk.columns))
        # Reset row labels so every series built below lines up with this chunk,
        # even for later chunks (whose labels start at 200,000, 400,000, ...).
        chunk = chunk.rename(columns=mapping).reset_index(drop=True)

        n = len(chunk)
        self.rows += n
        self.sources[source] += n

        for col in chunk.columns:
            self.blank_counts[col] += int((chunk[col].astype(str).str.strip() == "").sum())

        if "complaint_id" in chunk:
            # Store IDs as compact integer arrays; duplicates are counted once at the end.
            ids = pd.to_numeric(chunk["complaint_id"], errors="coerce")
            self.non_numeric_ids += int(ids.isna().sum())
            self.id_arrays.append(ids.dropna().astype("int64").to_numpy())

        dates = pd.to_datetime(chunk.get("date_received", pd.Series([""] * n)), errors="coerce", format="mixed")
        self.bad_dates += int(dates.isna().sum())
        if dates.notna().any():
            lo, hi = dates.min(), dates.max()
            self.min_date = lo if self.min_date is None else min(self.min_date, lo)
            self.max_date = hi if self.max_date is None else max(self.max_date, hi)
        years = dates.dt.year

        narrative = chunk.get("narrative", pd.Series([""] * n)).astype(str).str.strip()
        has_narr = narrative != ""
        self.with_narrative += int(has_narr.sum())

        for year, count in years.value_counts().items():
            self.by_year[int(year)] += int(count)
        for year, count in years[has_narr].value_counts().items():
            self.by_year_narr[int(year)] += int(count)

        narr = chunk[has_narr.values].assign(year=years[has_narr.values])
        if "product" in narr:
            for (product, year), count in narr.groupby(["product", "year"]).size().items():
                self.product_year[product][int(year)] += int(count)
            if "issue" in narr:
                for key, count in narr.groupby(["product", "issue"]).size().items():
                    self.issue_counts[key] += int(count)

        words = narrative[has_narr].str.split().str.len()
        for lo, hi in LENGTH_BUCKETS:
            self.length_buckets[(lo, hi)] += int(((words >= lo) & (words <= hi)).sum())

    @property
    def duplicate_ids(self) -> int:
        """Number of rows whose complaint ID already appeared earlier."""
        if not self.id_arrays:
            return 0
        all_ids = np.concatenate(self.id_arrays)
        return int(len(all_ids) - len(np.unique(all_ids)))


# ---------------------------------------------------------------- report

def _table(headers, rows) -> str:
    out = ["| " + " | ".join(headers) + " |", "| " + " | ".join("---" for _ in headers) + " |"]
    out += ["| " + " | ".join(str(c) for c in row) + " |" for row in rows]
    return "\n".join(out)


def render(p: Profile, batch: Path) -> str:
    pct = lambda a, b: f"{(100 * a / b):.1f}%" if b else "n/a"
    lines = [
        "# Raw data profile",
        "",
        f"Batch: `{batch.as_posix()}`",
        "",
        "## Overview",
        "",
        _table(["Measure", "Value"], [
            ["Rows", f"{p.rows:,}"],
            ["Rows with a narrative", f"{p.with_narrative:,} ({pct(p.with_narrative, p.rows)})"],
            ["Date range", f"{p.min_date:%Y-%m-%d} to {p.max_date:%Y-%m-%d}" if p.min_date is not None else "n/a"],
            ["Unreadable dates", f"{p.bad_dates:,}"],
            ["Duplicate complaint IDs", f"{p.duplicate_ids:,}"],
            ["Non-numeric complaint IDs", f"{p.non_numeric_ids:,}"],
            ["Missing required columns", ", ".join(sorted(p.missing_required)) or "none"],
        ]),
        "",
        "## Files read",
        "",
        _table(["Source", "Rows"], [[s, f"{n:,}"] for s, n in p.sources.items()]),
        "",
        "## Complaints per year",
        "",
        _table(["Year", "All", "With narrative", "Narrative share"],
               [[y, f"{p.by_year[y]:,}", f"{p.by_year_narr[y]:,}", pct(p.by_year_narr[y], p.by_year[y])] for y in sorted(p.by_year)]),
        "",
        "## Products by year (complaints with a narrative)",
        "",
        "A product that appears or disappears between years usually means CFPB renamed its categories.",
        "Pick a date range where the product list stays the same.",
        "",
    ]
    years = sorted(p.by_year_narr)
    products = sorted(p.product_year, key=lambda k: -sum(p.product_year[k].values()))
    lines.append(_table(["Product"] + [str(y) for y in years],
                        [[prod] + [f"{p.product_year[prod].get(y, 0):,}" for y in years] for prod in products]))
    lines += [
        "",
        "## Top 30 product / issue pairs (complaints with a narrative)",
        "",
        _table(["Product", "Issue", "Complaints"],
               [[prod, issue, f"{n:,}"] for (prod, issue), n in p.issue_counts.most_common(30)]),
        "",
        "## Narrative length (words)",
        "",
        _table(["Words", "Complaints"],
               [[f"{lo}-{hi}" if hi < 10**9 else f"{lo}+", f"{p.length_buckets[(lo, hi)]:,}"] for lo, hi in LENGTH_BUCKETS]),
        "",
        "## Blank values by column",
        "",
        _table(["Column", "Blank", "Share"],
               [[c, f"{p.blank_counts[c]:,}", pct(p.blank_counts[c], p.rows)] for c in sorted(p.blank_counts)]),
        "",
        "## Column name mapping",
        "",
        _table(["Raw header", "Standard name"], [[raw, std] for raw, std in p.columns_seen.items()]),
        "",
    ]
    return "\n".join(lines)


def data_files(batch: Path) -> list:
    """Data files in a bronze batch, excluding the manifest."""
    return sorted(
        f for f in batch.iterdir()
        if f.suffix.lower() in {".zip", ".csv", ".json"} and f.name != "manifest.json"
    )


def latest_batch(source_dir: Path) -> Path:
    """Most recent dated batch folder (one that has a manifest) under a source folder."""
    batches = sorted(d for d in source_dir.iterdir() if d.is_dir() and (d / "manifest.json").exists()) if source_dir.exists() else []
    if not batches:
        raise SystemExit(f"No batches in {source_dir}. Run `python -m src.ingest_bronze --source ...` first.")
    return batches[-1]


def main():
    parser = argparse.ArgumentParser(description="Profile a bronze batch of CFPB complaints.")
    parser.add_argument("--batch", type=Path, help="Bronze batch folder (default: latest)")
    parser.add_argument("--source", default="narratives", choices=["narratives", "live"])
    parser.add_argument("--bronze", type=Path, default=Path("data/bronze"))
    parser.add_argument("--out", type=Path, help="Report path (default: docs/data_profile_<source>.md)")
    args = parser.parse_args()

    batch = args.batch or latest_batch(args.bronze / args.source)
    args.out = args.out or Path(f"docs/data_profile_{args.source}.md")
    files = data_files(batch)
    if not files:
        raise SystemExit(f"No data files in {batch}")

    profile = Profile()
    for path in files:
        print(f"Reading {path.name} ...")
        for source, chunk in iter_chunks(path):
            profile.update(source, chunk)
            print(f"  {profile.rows:,} rows so far")

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(render(profile, batch), encoding="utf-8")
    summary = {"rows": profile.rows, "with_narrative": profile.with_narrative, "duplicate_ids": profile.duplicate_ids}
    print(json.dumps(summary, indent=2))
    print(f"Report written to {args.out}")


if __name__ == "__main__":
    main()
