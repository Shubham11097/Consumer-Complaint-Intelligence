"""CI performance gate.

Runs on every push in CI using the committed metrics files in reports/, so it
needs no data. It fails if:
  * the baseline is no better than always guessing the most common product, or
  * any other model's test macro-F1 is below the baseline's.
"""

import json
from pathlib import Path

import pytest

REPORTS = Path(__file__).resolve().parents[1] / "reports"
MIN_GAIN_OVER_DUMMY = 0.20


def _load(name):
    return json.loads((REPORTS / name).read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def baseline():
    path = REPORTS / "baseline_metrics.json"
    if not path.exists():
        pytest.skip("No baseline metrics yet: run `python -m src.train_baseline`")
    return _load(path.name)


def test_baseline_beats_dummy(baseline):
    test = baseline["splits"]["test"]["macro_f1"]
    dummy = baseline["dummy_most_frequent"]["test"]
    assert test >= dummy + MIN_GAIN_OVER_DUMMY, f"baseline {test:.3f} vs dummy {dummy:.3f}"


def test_baseline_covers_every_product(baseline):
    assert len(baseline["labels"]) == 11


def test_other_models_do_not_fall_below_baseline(baseline):
    floor = baseline["splits"]["test"]["macro_f1"]
    for path in sorted(REPORTS.glob("*_metrics.json")):
        if path.name == "baseline_metrics.json":
            continue
        score = _load(path.name)["splits"]["test"]["macro_f1"]
        assert score >= floor, f"{path.name}: test macro-F1 {score:.3f} is below the baseline {floor:.3f}"
