import pandas as pd

import src.build_gold as bg

CR = bg.CREDIT_REPORTING
OTHER_PRODUCTS = sorted(p for p in bg.KNOWN_PRODUCTS if p != CR)


def _meta():
    """Silver-style metadata covering train, validation and test months."""
    rows = []
    cid = 0

    def add(month, product, text, words=20):
        nonlocal cid
        cid += 1
        rows.append({"complaint_id": cid, "date_received": pd.Timestamp(f"{month}-15") + pd.Timedelta(minutes=cid),
                     "month": month, "product": product, "issue": "Some issue", "company": f"Co{cid % 4}",
                     "word_count": words, "text_hash": text})

    # Every product appears in train with unique text.
    for i, p in enumerate(OTHER_PRODUCTS):
        add("2024-01", p, f"train-{i}")
    # Credit reporting: 30 unique texts over 3 train months, plus a template used 6 times.
    for m in ["2024-01", "2024-02", "2024-03"]:
        for j in range(10):
            add(m, CR, f"cr-{m}-{j}")
    for m in ["2024-01", "2025-06", "2026-03", "2026-05", "2026-05", "2026-06"]:
        add(m, CR, "template-letter")
    # Validation and test complaints, one too short, one outside every split.
    add("2026-03", "Mortgage", "val-1")
    add("2026-04", "Credit card", "val-2")
    add("2026-05", "Debt collection", "test-1")
    add("2026-06", "Debt collection", "test-short", words=2)
    add("2022-10", "Mortgage", "too-early")
    return pd.DataFrame(rows)


def test_split_for_month():
    assert bg.split_for_month("2022-11") == "train"
    assert bg.split_for_month("2026-02") == "train"
    assert bg.split_for_month("2026-03") == "validation"
    assert bg.split_for_month("2026-07") == "test"
    assert bg.split_for_month("2022-10") is None
    assert bg.split_for_month("2026-08") is None


def test_template_kept_once_in_earliest_split():
    sel, steps = bg.select(_meta(), cap=1000)

    template = sel[sel["text_hash"] == "template-letter"]
    assert len(template) == 1
    assert template.iloc[0]["split"] == "train"          # earliest copy is from 2024-01
    assert template.iloc[0]["copies"] == 6
    assert bool(template.iloc[0]["is_template"])


def test_short_and_out_of_range_rows_dropped():
    sel, steps = bg.select(_meta(), cap=1000)

    assert "test-short" not in set(sel["text_hash"])
    assert "too-early" not in set(sel["text_hash"])
    assert steps["outside every split (dropped)"] == 1


def test_credit_reporting_capped_evenly_in_train_only():
    sel, steps = bg.select(_meta(), cap=12)

    train_cr = sel[(sel["split"] == "train") & (sel["product"] == CR)]
    assert len(train_cr) == 12
    assert train_cr["month"].value_counts().max() <= 4      # 12 spread over 3 months (+ template month)
    assert steps["credit reporting in train before cap"] == 31


def test_cap_is_reproducible():
    a, _ = bg.select(_meta(), cap=12)
    b, _ = bg.select(_meta(), cap=12)
    assert a["complaint_id"].tolist() == b["complaint_id"].tolist()


def test_checks_pass_on_clean_selection():
    sel, _ = bg.select(_meta(), cap=12)
    checks = bg.check_gold(sel, cap=12)
    assert all(c["passed"] for c in checks), [c for c in checks if not c["passed"]]


def test_checks_catch_leakage_and_missing_product():
    sel, _ = bg.select(_meta(), cap=12)
    leaked = pd.concat([sel, sel[sel["split"] == "train"].head(1).assign(split="test", complaint_id=999)])
    leaked = leaked[leaked["product"] != "Prepaid card"]

    failed = {c["check"] for c in bg.check_gold(leaked, cap=12) if not c["passed"]}

    assert "No text shared between splits (no leakage)" in failed
    assert "All 11 products present in train" in failed


def test_analytics_tables_count_all_complaints_and_templates():
    tables = bg.analytics_tables(_meta())
    t = tables["monthly_product_issue"]

    assert t["complaints"].sum() == len(_meta())
    may = t[(t["month"] == "2026-05") & (t["product"] == CR)]
    assert int(may["template_complaints"].iloc[0]) == 2


def test_build_end_to_end(tmp_path, monkeypatch):
    meta = _meta()
    text = meta[["complaint_id"]].assign(narrative_clean="some complaint text")
    parts = {"part-00001.parquet": text.iloc[:20], "part-00002.parquet": text.iloc[20:]}
    silver = tmp_path / "silver" / "2026-11-16"
    silver.mkdir(parents=True)
    for name in parts:
        (silver / name).write_bytes(b"")
    written = {}
    tables = {}
    monkeypatch.setattr(bg, "read_meta", lambda d: meta)
    monkeypatch.setattr(bg, "read_part", lambda p: parts[p.name])
    monkeypatch.setattr(bg, "write_part", lambda df, p: written.setdefault(p.parent.name, []).append(df))
    monkeypatch.setattr(bg, "write_table", lambda df, p: tables.setdefault(p.name, df))

    summary = bg.build(silver, tmp_path / "gold", tmp_path / "gold_report.md", cap=12)

    assert all(c["passed"] for c in summary["checks"])
    assert set(written) == {"train", "validation", "test"}
    assert sum(summary["rows_written"].values()) == summary["steps"]["model complaints"]
    train = pd.concat(written["train"])
    assert list(train.columns) == bg.GOLD_COLUMNS
    assert set(tables) == {"monthly_product_issue", "monthly_company_product"}
    assert "Products per split" in (tmp_path / "gold_report.md").read_text(encoding="utf-8")


def test_gold_parquet_round_trip(tmp_path):
    import pytest
    pytest.importorskip("pyarrow")
    df = pd.DataFrame({"complaint_id": [1, 2], "narrative_clean": ["a", "b"]})
    bg.write_part(df, tmp_path / "train" / "part-00001.parquet")
    bg.write_table(df, tmp_path / "analytics" / "t")

    assert len(pd.read_parquet(tmp_path / "train")) == 2
    assert (tmp_path / "analytics" / "t.csv").exists()
