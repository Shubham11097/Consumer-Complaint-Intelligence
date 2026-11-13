from src.columns import missing_columns, standardise_name


def test_csv_display_names_are_standardised():
    assert standardise_name("Date received") == "date_received"
    assert standardise_name("Sub-product") == "sub_product"
    assert standardise_name("Consumer consent provided?") == "consumer_consent_provided"
    assert standardise_name("Timely response?") == "timely_response"


def test_both_narrative_spellings_map_to_one_name():
    assert standardise_name("Consumer complaint narrative") == "narrative"
    assert standardise_name("complaint_what_happened") == "narrative"


def test_whitespace_and_case_are_ignored():
    assert standardise_name("  COMPLAINT ID ") == "complaint_id"


def test_missing_required_columns_are_reported():
    headers = ["Date received", "Product", "Issue", "Company"]
    assert missing_columns(headers) == ["complaint_id", "narrative"]


def test_no_missing_columns_when_all_present():
    headers = ["Complaint ID", "Date received", "Product", "Issue", "Consumer complaint narrative", "Company"]
    assert missing_columns(headers) == []
