import pandas as pd

from src.analyse_templates import analyse, render


def _silver():
    rows = []
    cid = 0
    # One template used 6 times (credit reporting), one used 5 times (debt collection),
    # a text used twice (not a template at threshold 5), and 4 unique texts.
    for text, product, n, month in [
        ("tmplA", "Credit reporting or other personal consumer reports", 6, "2025-06"),
        ("tmplB", "Debt collection", 5, "2025-07"),
        ("pair", "Credit card", 2, "2026-01"),
        ("u1", "Credit card", 1, "2026-01"),
        ("u2", "Mortgage", 1, "2026-02"),
        ("u3", "Mortgage", 1, "2026-02"),
        ("u4", "Debt collection", 1, "2025-07"),
    ]:
        for _ in range(n):
            cid += 1
            rows.append({"complaint_id": cid, "month": month, "product": product,
                         "company": f"Co{cid % 3}", "text_hash": text, "word_count": 40})
    return pd.DataFrame(rows)


def test_template_counts_and_one_copy_kept():
    r = analyse(_silver(), min_repeats=5)

    assert r["rows"] == 17
    assert r["template_texts"] == 2
    assert r["template_rows"] == 11
    assert r["rows_if_one_copy_kept"] == 17 - 11 + 2


def test_shares_by_product_and_group_sizes():
    r = analyse(_silver(), min_repeats=5)

    cr = r["by_product"].loc["Credit reporting or other personal consumer reports"]
    assert cr["template_share"] == 1.0
    assert r["by_product"].loc["Mortgage", "template_rows"] == 0
    sizes = r["group_sizes"].set_index("copies")
    assert sizes.loc["1 (unique)", "distinct_texts"] == 4
    assert sizes.loc["2–4", "complaints"] == 2
    assert sizes.loc["5–9", "distinct_texts"] == 2


def test_report_renders_with_previews_and_escapes_pipes():
    r = analyse(_silver(), min_repeats=5)
    text = render(r, {"tmplA": "I dispute | this item"}, min_repeats=5)

    assert "| 6 | Credit reporting" in text
    assert "I dispute \\| this item" in text
    assert "| 17 |" in text   # counts print as whole numbers


def test_previews_are_read_from_parquet(tmp_path):
    import pytest
    pytest.importorskip("pyarrow")
    from src.analyse_templates import load_previews
    silver = tmp_path / "2026-11-06"
    silver.mkdir()
    pd.DataFrame({"text_hash": ["a", "a", "b"], "narrative_clean": ["text A", "text A", "text B"]}).to_parquet(silver / "part-00001.parquet")
    pd.DataFrame({"text_hash": ["c"], "narrative_clean": ["text C"]}).to_parquet(silver / "part-00002.parquet")

    assert load_previews(silver, ["a", "c"]) == {"a": "text A", "c": "text C"}
