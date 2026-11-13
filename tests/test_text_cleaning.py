from src.text_cleaning import clean_narrative, has_content, text_hash, word_count


def test_redacted_dates_become_date_token():
    assert clean_narrative("On XX/XX/XXXX I called") == "On [DATE] I called"
    assert clean_narrative("Paid on XX/XX/2025.") == "Paid on [DATE] ."


def test_amounts_become_amount_token():
    assert clean_narrative("They charged {$1,250.00} twice") == "They charged [AMOUNT] twice"


def test_runs_of_redactions_collapse_to_one_token():
    assert clean_narrative("My name is XXXX XXXX and account XXXX") == "My name is [REDACTED] and account [REDACTED]"


def test_whitespace_is_tidied():
    assert clean_narrative("  too   many\n\nspaces  ") == "too many spaces"


def test_normal_words_with_x_are_untouched():
    assert clean_narrative("Xbox purchase and tax refund") == "Xbox purchase and tax refund"


def test_text_with_only_placeholders_has_no_content():
    assert not has_content(clean_narrative("XXXX XX/XX/XXXX {$5.00}"))
    assert has_content(clean_narrative("XXXX charged me"))


def test_non_text_input_is_handled():
    assert clean_narrative(None) == ""


def test_word_count_and_fingerprint():
    assert word_count("one two three") == 3
    assert word_count("") == 0
    assert text_hash("Same Text") == text_hash("same   text")
    assert text_hash("Same text") != text_hash("Different text")
