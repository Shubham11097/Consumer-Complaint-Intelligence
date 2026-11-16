"""Baseline classifier: TF-IDF + logistic regression, predicting the product.

This is the benchmark every later model (e.g. the fine-tuned transformer) must
beat. It trains on the gold training split, is scored on validation and test,
and is compared with a "dummy" model that always predicts the most common
product, as a sanity floor.

Outputs:
  models/baseline/model.joblib       trained pipeline (not committed to Git)
  reports/baseline_metrics.json      scores, read by the CI performance gate
  docs/baseline_report.md            human-readable results

Usage:
    python -m src.train_baseline
    python -m src.train_baseline --max-train-rows 0      # use every training row
"""

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.dummy import DummyClassifier
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, confusion_matrix, f1_score, precision_recall_fscore_support

from src.build_gold import SPLIT_ORDER

LABEL = "product"
TEXT = "narrative_clean"
SEED = 42
DEFAULT_MAX_TRAIN_ROWS = 300_000   # keeps memory use laptop-friendly; 0 = all rows
VOCAB_ROWS = 100_000               # rows used to learn the vocabulary
MAX_FEATURES = 100_000
TOP_WORDS = 12


# ---------------------------------------------------------------- data

def latest_gold(gold_root: Path) -> Path:
    runs = sorted(d for d in gold_root.iterdir() if (d / "model").is_dir()) if gold_root.exists() else []
    if not runs:
        raise SystemExit(f"No gold model data in {gold_root}. Run `python -m src.build_gold` first.")
    return runs[-1]


def load_split(gold_dir: Path, split: str) -> pd.DataFrame:
    return pd.read_parquet(gold_dir / "model" / split, columns=["complaint_id", "month", LABEL, TEXT])


def sample_rows(df: pd.DataFrame, n: int, seed: int = SEED) -> pd.DataFrame:
    """Random sample of n rows (keeps the product mix); n = 0 or n >= len means all rows."""
    return df if n <= 0 or n >= len(df) else df.sample(n=n, random_state=seed)


# ---------------------------------------------------------------- model

def make_vectorizer(max_features: int = MAX_FEATURES) -> TfidfVectorizer:
    return TfidfVectorizer(lowercase=True, ngram_range=(1, 2), min_df=5, max_df=0.5,
                           max_features=max_features, sublinear_tf=True, dtype=np.float32)


def train(train_df: pd.DataFrame, C: float = 1.0, vocab_rows: int = VOCAB_ROWS,
          max_features: int = MAX_FEATURES, seed: int = SEED):
    """Fit the vectorizer (on a subsample, to limit memory) and the classifier."""
    vectorizer = make_vectorizer(max_features)
    vectorizer.fit(sample_rows(train_df, vocab_rows, seed)[TEXT])
    X = vectorizer.transform(train_df[TEXT])
    classifier = LogisticRegression(C=C, class_weight="balanced", max_iter=300, random_state=seed)
    classifier.fit(X, train_df[LABEL])
    return vectorizer, classifier


def evaluate(y_true, y_pred, labels: list) -> dict:
    p, r, f, s = precision_recall_fscore_support(y_true, y_pred, labels=labels, zero_division=0)
    return {
        "rows": int(len(y_true)),
        "accuracy": float(accuracy_score(y_true, y_pred)),
        "macro_f1": float(f1_score(y_true, y_pred, labels=labels, average="macro", zero_division=0)),
        "weighted_f1": float(f1_score(y_true, y_pred, labels=labels, average="weighted", zero_division=0)),
        "per_class": {lab: {"precision": float(p[i]), "recall": float(r[i]), "f1": float(f[i]), "support": int(s[i])}
                      for i, lab in enumerate(labels)},
        "confusion_matrix": confusion_matrix(y_true, y_pred, labels=labels).tolist(),
    }


def top_words(vectorizer: TfidfVectorizer, classifier: LogisticRegression, n: int = TOP_WORDS) -> dict:
    """Words and phrases with the largest positive weight for each product."""
    names = np.asarray(vectorizer.get_feature_names_out())
    coef = classifier.coef_
    if coef.shape[0] == 1:   # binary case: one row of weights
        coef = np.vstack([-coef[0], coef[0]])
    return {lab: names[np.argsort(coef[i])[::-1][:n]].tolist() for i, lab in enumerate(classifier.classes_)}


def run(splits: dict, C: float = 1.0, max_train_rows: int = DEFAULT_MAX_TRAIN_ROWS,
        vocab_rows: int = VOCAB_ROWS, max_features: int = MAX_FEATURES, seed: int = SEED) -> tuple:
    """Train on splits['train'], evaluate on every split. Returns (vectorizer, classifier, metrics)."""
    train_df = sample_rows(splits["train"], max_train_rows, seed)
    labels = sorted(splits["train"][LABEL].unique())
    print(f"Training on {len(train_df):,} complaints, {len(labels)} products ...")
    vectorizer, classifier = train(train_df, C, vocab_rows, max_features, seed)

    dummy = DummyClassifier(strategy="most_frequent").fit(np.zeros((len(train_df), 1)), train_df[LABEL])
    metrics = {
        "model": "baseline_tfidf_logreg",
        "trained_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "params": {"C": C, "train_rows": len(train_df), "vocab_rows": vocab_rows,
                   "max_features": max_features, "ngram_range": [1, 2], "class_weight": "balanced", "seed": seed},
        "labels": labels,
        "splits": {},
        "dummy_most_frequent": {},
        "top_words": top_words(vectorizer, classifier),
    }
    for split in [s for s in SPLIT_ORDER if s in splits]:
        df = splits[split]
        if split == "train":
            df = train_df
        pred = classifier.predict(vectorizer.transform(df[TEXT]))
        metrics["splits"][split] = evaluate(df[LABEL], pred, labels)
        dummy_pred = dummy.predict(np.zeros((len(df), 1)))
        metrics["dummy_most_frequent"][split] = float(
            f1_score(df[LABEL], dummy_pred, labels=labels, average="macro", zero_division=0))
        print(f"  {split}: macro-F1 {metrics['splits'][split]['macro_f1']:.3f}, "
              f"accuracy {metrics['splits'][split]['accuracy']:.3f}")
    return vectorizer, classifier, metrics


# ---------------------------------------------------------------- report

def short(label: str, n: int = 32) -> str:
    return label if len(label) <= n else label[: n - 1] + "…"


def render_report(m: dict) -> str:
    labels = m["labels"]
    lines = [
        "# Baseline model report",
        "",
        "TF-IDF (words and two-word phrases) + logistic regression with balanced class weights, predicting the **product**.",
        f"Trained {m['trained_at_utc']} on {m['params']['train_rows']:,} complaints from the gold training split.",
        "",
        "## Scores",
        "",
        "| Split | Complaints | Macro-F1 | Accuracy | Weighted F1 | Dummy macro-F1 |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for split, s in m["splits"].items():
        lines.append(f"| {split} | {s['rows']:,} | **{s['macro_f1']:.3f}** | {s['accuracy']:.3f} | "
                     f"{s['weighted_f1']:.3f} | {m['dummy_most_frequent'][split]:.3f} |")
    lines += [
        "",
        "Macro-F1 gives every product equal weight, so small products count as much as large ones. "
        "The dummy model always predicts the most common product and sets the floor.",
        "",
        "## Per product (test split)",
        "",
        "| Product | Precision | Recall | F1 | Complaints |",
        "| --- | --- | --- | --- | --- |",
    ]
    test = m["splits"].get("test") or next(iter(m["splits"].values()))
    for lab in sorted(labels, key=lambda l: -test["per_class"][l]["f1"]):
        c = test["per_class"][lab]
        lines.append(f"| {lab} | {c['precision']:.3f} | {c['recall']:.3f} | {c['f1']:.3f} | {c['support']:,} |")
    lines += [
        "",
        "## Confusion matrix (test split)",
        "",
        "Rows are the true product, columns the predicted product.",
        "",
        "| True \\ Predicted | " + " | ".join(short(l, 14) for l in labels) + " |",
        "| --- | " + " | ".join("---" for _ in labels) + " |",
    ]
    for lab, row in zip(labels, test["confusion_matrix"]):
        lines.append(f"| {short(lab)} | " + " | ".join(f"{v:,}" for v in row) + " |")
    lines += ["", "## Words that drive each product", "", "| Product | Top words and phrases |", "| --- | --- |"]
    for lab in labels:
        lines.append(f"| {lab} | {', '.join(m['top_words'][lab])} |")
    return "\n".join(lines) + "\n"


def main():
    parser = argparse.ArgumentParser(description="Train and evaluate the TF-IDF + logistic regression baseline.")
    parser.add_argument("--gold", type=Path, default=Path("data/gold"))
    parser.add_argument("--C", type=float, default=1.0, help="Inverse regularisation strength")
    parser.add_argument("--max-train-rows", type=int, default=DEFAULT_MAX_TRAIN_ROWS, help="0 = all rows")
    parser.add_argument("--model-dir", type=Path, default=Path("models/baseline"))
    parser.add_argument("--metrics", type=Path, default=Path("reports/baseline_metrics.json"))
    parser.add_argument("--report", type=Path, default=Path("docs/baseline_report.md"))
    args = parser.parse_args()

    gold_dir = latest_gold(args.gold)
    print(f"Loading gold data from {gold_dir} ...")
    splits = {s: load_split(gold_dir, s) for s in SPLIT_ORDER}
    vectorizer, classifier, metrics = run(splits, C=args.C, max_train_rows=args.max_train_rows)
    metrics["gold"] = gold_dir.as_posix()

    args.model_dir.mkdir(parents=True, exist_ok=True)
    joblib.dump({"vectorizer": vectorizer, "classifier": classifier}, args.model_dir / "model.joblib")
    args.metrics.parent.mkdir(parents=True, exist_ok=True)
    args.metrics.write_text(json.dumps(metrics, indent=2), encoding="utf-8")
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(render_report(metrics), encoding="utf-8")
    print(f"Model saved to {args.model_dir / 'model.joblib'}")
    print(f"Metrics: {args.metrics} · Report: {args.report}")


if __name__ == "__main__":
    main()
