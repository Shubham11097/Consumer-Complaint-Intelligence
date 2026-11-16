"""Map CFPB's pre-August-2023 category names onto the current ones.

In August 2023 the CFPB reorganised its product categories. Complaints before
then use older names; some old products were split by sub-product. Mapping them
gives one consistent set of 11 products across the whole date range.

Checked against the raw exports (narratives archive):
  * "Credit reporting, credit repair services, or other personal consumer reports"
      - sub-product "Credit repair services" -> "Debt or credit management"
        (current data files credit repair under Debt or credit management)
      - every other sub-product              -> "Credit reporting or other personal consumer reports"
  * "Credit card or prepaid card"
      - credit card sub-products             -> "Credit card"
      - prepaid, gift, payroll, benefit cards -> "Prepaid card"
  * "Payday loan, title loan, or personal loan"
                                             -> "Payday loan, title loan, personal loan, or advance loan"

The original values are kept in product_original / issue_original. A product
not covered here stays as it is, so the silver "Product in known list" check
stops the build and the mapping can be extended.
"""

import pandas as pd

CREDIT_REPORTING_OLD = "Credit reporting, credit repair services, or other personal consumer reports"
CARD_OLD = "Credit card or prepaid card"
PAYDAY_OLD = "Payday loan, title loan, or personal loan"

CREDIT_REPORTING = "Credit reporting or other personal consumer reports"
DEBT_MANAGEMENT = "Debt or credit management"
CREDIT_CARD = "Credit card"
PREPAID_CARD = "Prepaid card"
PAYDAY = "Payday loan, title loan, personal loan, or advance loan"

CREDIT_CARD_SUB_PRODUCTS = {"General-purpose credit card or charge card", "Store credit card"}

ISSUE_RENAMES = {
    "Problem with a credit reporting company's investigation into an existing problem":
        "Problem with a company's investigation into an existing problem",
}


def map_product(product: str, sub_product: str) -> str:
    """Current product name for one complaint."""
    if product == CREDIT_REPORTING_OLD:
        return DEBT_MANAGEMENT if sub_product == "Credit repair services" else CREDIT_REPORTING
    if product == CARD_OLD:
        return CREDIT_CARD if sub_product in CREDIT_CARD_SUB_PRODUCTS else PREPAID_CARD
    if product == PAYDAY_OLD:
        return PAYDAY
    return product


def map_categories(df: pd.DataFrame) -> pd.DataFrame:
    """Return df with current product and issue names; originals kept alongside."""
    df = df.copy()
    df["product_original"] = df["product"]
    df["issue_original"] = df["issue"]
    df["product"] = [map_product(p, s) for p, s in zip(df["product"], df["sub_product"])]
    df["issue"] = df["issue"].replace(ISSUE_RENAMES)
    return df
