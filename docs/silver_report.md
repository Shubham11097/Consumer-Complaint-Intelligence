# Silver layer report

Bronze batch: `data/bronze/narratives/2026-11-06` · built 2026-11-13T06:53:30+00:00

## Rows

| Step | Rows |
| --- | --- |
| Read from bronze | 8,816,336 |
| Dropped: duplicate complaint ID | 0 |
| Dropped: no narrative | 7,738,298 |
| Dropped: only redaction placeholders | 434 |
| Dropped: unreadable ID or date | 0 |
| **Written to silver** | **1,077,604** |

## Repeated (template) texts

7,219 distinct texts appear 5 or more times, covering 416,100 complaints. They are kept in silver and flagged by `text_hash`; the gold layer decides whether to remove them.

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
| Narrative at least 3 words | warning | FAIL | 19 |
