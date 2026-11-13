import zipfile

import pandas as pd

from src.profile_raw import Profile, iter_chunks

ROWS = pd.DataFrame({
    "Complaint ID": ["1", "2", "3", "3"],
    "Date received": ["2023-01-05", "2023-06-10", "2024-02-01", "2024-02-01"],
    "Product": ["Credit card", "Mortgage", "Credit card", "Credit card"],
    "Issue": ["Fees", "Payments", "Fees", "Fees"],
    "Consumer complaint narrative": ["I was charged a fee", "", "Unexpected fee again", "Unexpected fee again"],
    "Company": ["Bank A", "Bank B", "Bank A", "Bank A"],
})


def _profile_of(path):
    profile = Profile()
    for source, chunk in iter_chunks(path):
        profile.update(source, chunk)
    return profile


def test_profile_counts_rows_narratives_and_duplicates(tmp_path):
    csv = tmp_path / "sample.csv"
    ROWS.to_csv(csv, index=False)

    p = _profile_of(csv)

    assert p.rows == 4
    assert p.with_narrative == 3
    assert p.duplicate_ids == 1
    assert p.by_year[2023] == 2 and p.by_year_narr[2023] == 1
    assert p.product_year["Credit card"][2024] == 2
    assert p.missing_required == set()


def test_csv_inside_zip_is_read(tmp_path):
    csv = tmp_path / "sample.csv"
    ROWS.to_csv(csv, index=False)
    archive = tmp_path / "export.zip"
    with zipfile.ZipFile(archive, "w") as z:
        z.write(csv, arcname="complaints.csv")

    p = _profile_of(archive)

    assert p.rows == 4
    assert "export.zip/complaints.csv" in p.sources


def test_json_export_is_read(tmp_path):
    js = tmp_path / "sample.json"
    ROWS.rename(columns={"Consumer complaint narrative": "complaint_what_happened"}).to_json(js, orient="records")

    p = _profile_of(js)

    assert p.rows == 4
    assert p.with_narrative == 3


def test_manifest_is_not_treated_as_data(tmp_path):
    from src.profile_raw import data_files
    (tmp_path / "manifest.json").write_text("{}", encoding="utf-8")
    (tmp_path / "export.zip").write_bytes(b"")

    assert [f.name for f in data_files(tmp_path)] == ["export.zip"]


def test_later_chunks_and_missing_columns_do_not_break_profiling(tmp_path, monkeypatch):
    # Regression test: the second chunk of a large file has row labels starting
    # at CHUNK_ROWS; with a column missing this used to raise IndexingError.
    import src.profile_raw as pr
    monkeypatch.setattr(pr, "CHUNK_ROWS", 2)
    csv = tmp_path / "no_narrative.csv"
    ROWS.drop(columns=["Consumer complaint narrative"]).to_csv(csv, index=False)

    p = _profile_of(csv)

    assert p.rows == 4
    assert p.with_narrative == 0
    assert "narrative" in p.missing_required


def test_monthly_counts_and_category_changes(tmp_path, monkeypatch):
    import src.profile_raw as pr
    monkeypatch.setattr(pr, "MIN_ISSUE_COUNT", 1)
    rows = pd.DataFrame({
        "Complaint ID": ["1", "2", "3", "4"],
        "Date received": ["2026-01-10", "2026-02-10", "2026-03-10", "2026-03-11"],
        "Product": ["Credit card", "Credit card", "Credit card", "Prepaid card"],
        "Issue": ["Old fee name", "Old fee name", "New fee name", "Fees"],
        "Consumer complaint narrative": ["text", "text", "text", "text"],
        "Company": ["A", "A", "A", "B"],
    })
    csv = tmp_path / "months.csv"
    rows.to_csv(csv, index=False)

    p = _profile_of(csv)
    changes = {(kind, name): (first, last) for kind, name, first, last, _ in p.category_changes()}

    assert p.by_month_narr["2026-03"] == 2
    assert p.product_month["Credit card"]["2026-01"] == 1
    assert changes[("Product", "Prepaid card")] == ("2026-03", "2026-03")
    assert changes[("Issue", "Credit card / Old fee name")] == ("2026-01", "2026-02")
    assert changes[("Issue", "Credit card / New fee name")] == ("2026-03", "2026-03")
    assert ("Product", "Credit card") not in changes
