import json
import zipfile

import pandas as pd

import src.build_silver as bs
from src.silver_checks import check_chunk, summarise

BRONZE_ROWS = pd.DataFrame({
    "Complaint ID": ["1", "2", "3", "4", "5", "5"],
    "Date received": ["2026-01-05", "2026-01-06", "2026-02-01", "2026-02-02", "2026-03-01", "2026-03-01"],
    "Product": ["Credit card", "Mortgage", "Credit card", "Debt collection", "Credit card", "Credit card"],
    "Sub-product": ["General-purpose credit card", "", "", "", "", ""],
    "Issue": ["Fees or interest", "Struggling to pay mortgage", "Fees or interest", "Attempts to collect debt not owed", "Fees or interest", "Fees or interest"],
    "Sub-issue": ["", "", "", "", "", ""],
    "Consumer complaint narrative": [
        "On XX/XX/XXXX they charged me {$35.00} in fees",
        "",                                   # no narrative -> dropped
        "XXXX XX/XX/XXXX",                    # only placeholders -> dropped
        "I do not owe this debt to XXXX",
        "Late fee was added again",
        "Late fee was added again",           # duplicate complaint ID -> dropped
    ],
    "Company": ["Bank A", "Bank B", "Bank A", "Agency C", "Bank A", "Bank A"],
    "State": ["CA", "TX", "NY", "FL", "CA", "CA"],
    "Submitted via": ["Web"] * 6,
    "Company response to consumer": ["Closed with explanation"] * 6,
    "Timely response?": ["Yes", "Yes", "No", "Yes", "No", "No"],
})


def test_transform_chunk_cleans_types_and_drops_rows():
    df, dropped = bs.transform_chunk(BRONZE_ROWS, "test.csv")

    assert dropped["no narrative"] == 1
    assert dropped["only redaction placeholders"] == 1
    assert list(df.columns) == bs.SILVER_COLUMNS
    assert df.loc[0, "narrative_clean"] == "On [DATE] they charged me [AMOUNT] in fees"
    assert df.loc[0, "narrative"].startswith("On XX/XX/XXXX")   # original kept
    assert str(df["complaint_id"].dtype) == "Int64"
    assert pd.api.types.is_datetime64_any_dtype(df["date_received"])
    assert df.loc[0, "month"] == "2026-01"
    assert df.loc[0, "timely_response"] == True  # noqa: E712
    assert df["word_count"].min() > 0


def test_checks_catch_unknown_product_and_duplicates():
    df, _ = bs.transform_chunk(BRONZE_ROWS, "test.csv")
    df = df.drop_duplicates("complaint_id")
    bad = pd.concat([df, df.head(1)], ignore_index=True)
    bad.loc[0, "product"] = "Brand new product"

    result = check_chunk(bad)

    assert result["Product in known list"] == 1
    assert result["Complaint ID unique"] == 2


def test_clean_data_passes_all_error_checks():
    df, _ = bs.transform_chunk(BRONZE_ROWS, "test.csv")
    df = df.drop_duplicates("complaint_id")
    summary = summarise([check_chunk(df)], len(df))
    assert all(c["passed"] for c in summary if c["severity"] == "error")


def _bronze_batch(tmp_path, rows=BRONZE_ROWS):
    batch = tmp_path / "bronze" / "narratives" / "2026-11-06"
    batch.mkdir(parents=True)
    csv = tmp_path / "export.csv"
    rows.to_csv(csv, index=False)
    with zipfile.ZipFile(batch / "export.zip", "w") as z:
        z.write(csv, arcname="export.csv")
    (batch / "manifest.json").write_text("{}", encoding="utf-8")
    return batch


def test_build_end_to_end_with_dedupe_and_report(tmp_path, monkeypatch):
    written = []
    monkeypatch.setattr(bs, "write_part", lambda df, path: written.append(df))
    batch = _bronze_batch(tmp_path)

    summary = bs.build(batch, tmp_path / "silver", tmp_path / "report.md")

    assert summary["rows_read"] == 6
    assert summary["rows_written"] == 3
    assert summary["rows_dropped"]["duplicate complaint ID"] == 1
    assert sorted(pd.concat(written)["complaint_id"].tolist()) == [1, 4, 5]
    assert all(c["passed"] for c in summary["checks"] if c["severity"] == "error")
    assert "Written to silver" in (tmp_path / "report.md").read_text(encoding="utf-8")
    saved = json.loads((tmp_path / "silver" / "2026-11-06" / "_summary.json").read_text(encoding="utf-8"))
    assert saved["rows_written"] == 3


def test_build_writes_readable_parquet(tmp_path):
    import pytest
    pytest.importorskip("pyarrow")
    batch = _bronze_batch(tmp_path)

    bs.build(batch, tmp_path / "silver", tmp_path / "report.md")
    silver = pd.read_parquet(tmp_path / "silver" / "2026-11-06")

    assert len(silver) == 3
    assert set(silver["product"]) == {"Credit card", "Debt collection"}


def test_chunk_without_any_narratives_returns_empty_result():
    # Regression test: 2026 chunks often contain no narratives at all,
    # which used to crash with "invalid literal for int()".
    no_text = BRONZE_ROWS.assign(**{"Consumer complaint narrative": ""})

    df, dropped = bs.transform_chunk(no_text, "test.csv")

    assert df.empty
    assert list(df.columns) == bs.SILVER_COLUMNS
    assert dropped["no narrative"] == len(no_text)


def test_build_handles_chunks_with_no_narratives(tmp_path, monkeypatch):
    import src.profile_raw as pr
    monkeypatch.setattr(pr, "CHUNK_ROWS", 2)   # 6 rows -> 3 chunks
    written = []
    monkeypatch.setattr(bs, "write_part", lambda df, path: written.append(df))
    # Reorder so the middle chunk holds only the "no narrative" and "placeholders only" rows.
    batch = _bronze_batch(tmp_path, BRONZE_ROWS.iloc[[0, 3, 1, 2, 4, 5]])

    summary = bs.build(batch, tmp_path / "silver", tmp_path / "report.md")

    assert summary["rows_written"] == 3
    assert summary["part_files"] == 2
