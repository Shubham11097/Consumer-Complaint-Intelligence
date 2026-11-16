import pandas as pd

from src.category_mapping import map_categories, map_product
from src.silver_checks import KNOWN_PRODUCTS


def test_old_credit_reporting_splits_out_credit_repair():
    old = "Credit reporting, credit repair services, or other personal consumer reports"
    assert map_product(old, "Credit reporting") == "Credit reporting or other personal consumer reports"
    assert map_product(old, "Other personal consumer report") == "Credit reporting or other personal consumer reports"
    assert map_product(old, "Credit repair services") == "Debt or credit management"


def test_old_card_product_splits_by_sub_product():
    old = "Credit card or prepaid card"
    assert map_product(old, "General-purpose credit card or charge card") == "Credit card"
    assert map_product(old, "Store credit card") == "Credit card"
    for prepaid in ["General-purpose prepaid card", "Government benefit card", "Gift card", "Payroll card", "Student prepaid card"]:
        assert map_product(old, prepaid) == "Prepaid card"


def test_old_payday_name_and_current_names():
    assert map_product("Payday loan, title loan, or personal loan", "Title loan") == \
        "Payday loan, title loan, personal loan, or advance loan"
    assert map_product("Mortgage", "Conventional home mortgage") == "Mortgage"


def test_every_mapped_product_is_a_known_product():
    old_pairs = [
        ("Credit reporting, credit repair services, or other personal consumer reports", "Credit reporting"),
        ("Credit reporting, credit repair services, or other personal consumer reports", "Credit repair services"),
        ("Credit card or prepaid card", "Store credit card"),
        ("Credit card or prepaid card", "Gift card"),
        ("Payday loan, title loan, or personal loan", "Payday loan"),
    ]
    assert all(map_product(p, s) in KNOWN_PRODUCTS for p, s in old_pairs)


def test_map_categories_keeps_originals_and_renames_issue():
    df = pd.DataFrame({
        "product": ["Credit card or prepaid card", "Mortgage"],
        "sub_product": ["Gift card", ""],
        "issue": ["Problem with a credit reporting company's investigation into an existing problem", "Trouble during payment process"],
    })
    out = map_categories(df)

    assert out["product"].tolist() == ["Prepaid card", "Mortgage"]
    assert out["product_original"].tolist() == ["Credit card or prepaid card", "Mortgage"]
    assert out.loc[0, "issue"] == "Problem with a company's investigation into an existing problem"
    assert out.loc[0, "issue_original"].startswith("Problem with a credit reporting company")
