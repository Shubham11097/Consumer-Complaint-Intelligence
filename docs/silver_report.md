# Silver layer report

Bronze batches: `data/bronze/narratives/2026-11-06`, `data/bronze/narratives/2026-11-16` · built 2026-11-16T08:36:39+00:00

## Rows

| Step | Rows |
| --- | --- |
| Read from bronze | 13,815,857 |
| Dropped: duplicate complaint ID | 0 |
| Dropped: no narrative | 11,103,923 |
| Dropped: only redaction placeholders | 1,007 |
| Dropped: unreadable ID or date | 0 |
| **Written to silver** | **2,710,927** |

## Old category names mapped to current ones

| Old product  ->  current product | Complaints |
| --- | --- |
| Credit reporting, credit repair services, or other personal consumer reports  ->  Credit reporting or other personal consumer reports | 272,538 |
| Credit card or prepaid card  ->  Credit card | 23,315 |
| Payday loan, title loan, or personal loan  ->  Payday loan, title loan, personal loan, or advance loan | 3,379 |
| Credit card or prepaid card  ->  Prepaid card | 2,023 |
| Credit reporting, credit repair services, or other personal consumer reports  ->  Debt or credit management | 799 |

## Repeated (template) texts

19,295 distinct texts appear 5 or more times, covering 1,002,550 complaints. They are kept in silver and flagged by `text_hash`; the gold layer decides whether to remove them.

## Data-quality checks

| Check | Severity | Result | Failing rows |
| --- | --- | --- | --- |
| Complaint ID present | error | Pass | 0 |
| Complaint ID unique | error | Pass | 0 |
| Date received present | error | Pass | 0 |
| Date received not in the future | error | Pass | 0 |
| Product in known list | error | Pass | 0 |
| Issue not blank | error | Pass | 0 |
| Narrative has real words | error | Pass | 0 |
| Company not blank | warning | Pass | 0 |
| Narrative at least 3 words | warning | FAIL | 218 |
