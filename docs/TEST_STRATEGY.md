# Test strategy

Risk-based: each risk to the project is matched to the test that catches it. Tests are added layer by layer as the pipeline grows.

| Risk | Where | Test | Tool | Status |
| --- | --- | --- | --- | --- |
| Raw file altered or corrupted while storing | Bronze | Checksum verified after copy | pytest | Done |
| Same file loaded twice | Bronze | Re-ingesting a known file is skipped | pytest | Done |
| Column names differ between CSV and JSON exports | Bronze → Silver | Both spellings map to one standard name | pytest | Done |
| Required columns missing from an export | Bronze → Silver | Missing columns reported | pytest | Done |
| Duplicate complaint IDs | Silver | Duplicates removed across all files; uniqueness check on every chunk | Silver checks + pytest | Done |
| Empty or redaction-only narratives | Silver | Rows with only XXXX / date / amount placeholders dropped; check that every narrative has real words | Silver checks + pytest | Done |
| Category names change over time | Bronze → Silver | Monthly category-change report; build fails if a product is outside the known list of 11 | Profiler + silver checks + pytest | Done |
| Redaction patterns not handled (names, dates, amounts) | Silver | Placeholder rules tested on real CFPB patterns, normal words like "Xbox" untouched | pytest | Done |
| Unreadable IDs or dates | Silver | Rows dropped and counted; checks for missing IDs, missing dates, future dates | Silver checks + pytest | Done |
| Repeated template complaints inflate one class | Silver → Gold | Text fingerprint; texts repeated 5+ times counted in silver report | Silver report | Flagged; handled in gold |
| Same complaint in train and test sets | Gold | No ID overlap between splits | pytest | Planned |
| Model gets worse after a change | Model | CI gate: macro-F1 must not fall below baseline | pytest + GitHub Actions | Planned |
| Model relies on irrelevant words | Model | Prediction unchanged when company name or amount changes | pytest | Planned |
| Broken deployment | Dev → Prod | Smoke tests in dev before approval to prod | GitHub Actions | Planned |
