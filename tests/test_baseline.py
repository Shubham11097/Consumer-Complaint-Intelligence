import numpy as np
import pandas as pd

import src.train_baseline as tb

WORDS = {
    "Mortgage": "escrow loan modification foreclosure servicer",
    "Credit card": "card statement interest charge limit",
    "Debt collection": "collector debt owe validation letter",
}


def _split(n_per_class, seed):
    rng = np.random.default_rng(seed)
    rows = []
    for product, words in WORDS.items():
        vocab = words.split()
        for i in range(n_per_class):
            text = " ".join(rng.choice(vocab, 6)) + " the company did not help me"
            rows.append({"complaint_id": len(rows) + 1, "month": "2024-01", "product": product, "narrative_clean": text})
    return pd.DataFrame(rows)


def _splits():
    return {"train": _split(60, 0), "validation": _split(15, 1), "test": _split(15, 2)}


def test_baseline_learns_clear_signal_and_beats_dummy():
    _, _, m = tb.run(_splits(), max_train_rows=0, vocab_rows=0, max_features=1000)

    assert m["labels"] == sorted(WORDS)
    assert m["splits"]["test"]["macro_f1"] > 0.95
    assert m["splits"]["test"]["macro_f1"] > m["dummy_most_frequent"]["test"] + 0.5
    assert set(m["splits"]) == {"train", "validation", "test"}


def test_top_words_point_to_each_product():
    _, _, m = tb.run(_splits(), max_train_rows=0, vocab_rows=0, max_features=1000)

    top = {lab: " ".join(words) for lab, words in m["top_words"].items()}
    assert "escrow" in top["Mortgage"] or "foreclosure" in top["Mortgage"]
    assert "collector" in top["Debt collection"] or "debt" in top["Debt collection"]


def test_evaluate_metrics_and_confusion_matrix():
    labels = ["a", "b"]
    m = tb.evaluate(["a", "a", "b", "b"], ["a", "b", "b", "b"], labels)

    assert m["accuracy"] == 0.75
    assert m["confusion_matrix"] == [[1, 1], [0, 2]]
    assert m["per_class"]["a"]["recall"] == 0.5


def test_sample_rows_respects_limits():
    df = _split(10, 0)
    assert len(tb.sample_rows(df, 0)) == len(df)
    assert len(tb.sample_rows(df, 5)) == 5
    assert tb.sample_rows(df, 5)["complaint_id"].tolist() == tb.sample_rows(df, 5)["complaint_id"].tolist()


def test_report_renders():
    _, _, m = tb.run(_splits(), max_train_rows=0, vocab_rows=0, max_features=1000)
    text = tb.render_report(m)

    assert "## Scores" in text and "## Confusion matrix (test split)" in text
    assert "| Mortgage |" in text
