# Test strategy

Risk-based: each risk to the project is matched to the test that catches it. Tests are added layer by layer as the pipeline grows.

| Risk | Where | Test | Tool | Status |
| --- | --- | --- | --- | --- |
| Raw file altered or corrupted while storing | Bronze | Checksum verified after copy | pytest | Done |
| Same file loaded twice | Bronze | Re-ingesting a known file is skipped | pytest | Done |
| Column names differ between CSV and JSON exports | Bronze → Silver | Both spellings map to one standard name | pytest | Done |
| Required columns missing from an export | Bronze → Silver | Missing columns reported | pytest | Done |
| Duplicate complaint IDs | Silver | Uniqueness check | pytest / Great Expectations | Profiled; check planned |
| Empty or redaction-only narratives | Silver | Narrative not empty after cleaning | Great Expectations | Planned |
| Category names change over time | Silver | Values in allowed list for chosen date range | Great Expectations | Planned |
| Same complaint in train and test sets | Gold | No ID overlap between splits | pytest | Planned |
| Model gets worse after a change | Model | CI gate: macro-F1 must not fall below baseline | pytest + GitHub Actions | Planned |
| Model relies on irrelevant words | Model | Prediction unchanged when company name or amount changes | pytest | Planned |
| Broken deployment | Dev → Prod | Smoke tests in dev before approval to prod | GitHub Actions | Planned |
