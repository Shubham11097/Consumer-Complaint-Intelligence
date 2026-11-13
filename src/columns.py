"""Column name handling for CFPB complaint exports.

CFPB files come in two naming styles:
  * CSV exports use display names, e.g. "Date received", "Consumer complaint narrative"
  * JSON/API exports use snake_case, e.g. "date_received", "complaint_what_happened"

Everything downstream uses one standard set of snake_case names, defined here.
"""

import re

# Standard column names used throughout the project.
STANDARD_COLUMNS = [
    "complaint_id",
    "date_received",
    "product",
    "sub_product",
    "issue",
    "sub_issue",
    "narrative",
    "company_public_response",
    "company",
    "state",
    "zip_code",
    "tags",
    "consumer_consent_provided",
    "submitted_via",
    "date_sent_to_company",
    "company_response_to_consumer",
    "timely_response",
    "consumer_disputed",
]

# Known variants (after basic cleaning) mapped to the standard name.
ALIASES = {
    "consumer_complaint_narrative": "narrative",
    "complaint_what_happened": "narrative",
    "subproduct": "sub_product",
    "subissue": "sub_issue",
}


def standardise_name(name: str) -> str:
    """Map a raw CFPB column header to the project's standard name.

    "Consumer complaint narrative" -> "narrative"
    "Consumer consent provided?"   -> "consumer_consent_provided"
    "Sub-product"                  -> "sub_product"
    """
    cleaned = re.sub(r"[^a-z0-9]+", "_", str(name).strip().lower()).strip("_")
    return ALIASES.get(cleaned, cleaned)


def standardise_columns(columns) -> dict:
    """Return a {raw_name: standard_name} mapping for a list of headers."""
    return {col: standardise_name(col) for col in columns}


def missing_columns(columns, required=("complaint_id", "date_received", "product", "issue", "narrative", "company")) -> list:
    """List required standard columns that are absent from the given headers."""
    present = {standardise_name(c) for c in columns}
    return [c for c in required if c not in present]
