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
| Repeated template complaints inflate one class | Silver → Gold | Text fingerprint in silver; template analysis report; one copy kept in gold | Silver report + gold | Done |
| Same complaint in train and test sets | Gold | Build fails if a complaint ID is in more than one split | Gold checks + pytest | Done |
| Same template letter in train and test (leakage) | Gold | One copy of each exact text kept (earliest); build fails if a text is in more than one split | Gold checks + pytest | Done |
| Future data leaks into training | Gold | Build fails unless train < validation < test in time | Gold checks + pytest | Done |
| One product dominates training | Gold | Credit reporting capped in train, sampled evenly across months; build fails if over the cap | Gold checks + pytest | Done |
| A product missing from training | Gold | Build fails if any of the 11 products is absent from train | Gold checks + pytest | Done |
| Model gets worse after a change | Model | Performance gate on committed metrics: baseline must beat the always-most-common guess by 0.20 macro-F1; every other model must match or beat the baseline on test macro-F1 | pytest (GitHub Actions next) | Done |
| Model relies on irrelevant words | Model | Prediction unchanged when company name or amount changes | pytest | Planned |
| Broken deployment | Dev → Prod | Smoke tests in dev before approval to prod | GitHub Actions | Planned |
