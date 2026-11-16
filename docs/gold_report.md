# Gold layer report

Silver: `data/silver/narratives/2026-11-16` · built 2026-11-16T09:28:32+00:00

## Model data: how rows were selected

| Step | Complaints |
| --- | --- |
| silver complaints | 2,710,927 |
| after keeping one copy of each text | 1,454,276 |
| after dropping narratives under 3 words | 1,454,199 |
| outside every split (dropped) | 0 |
| credit reporting in train before cap | 791,887 |
| credit reporting in train after cap | 48,079 |
| model complaints | 710,391 |

## Splits

| Split | Months | Complaints | Template share |
| --- | --- | --- | --- |
| train | 2022-11 – 2026-02 | 632,742 | 0.4% |
| validation | 2026-03 – 2026-04 | 37,903 | 0.2% |
| test | 2026-05 – 2026-07 | 39,746 | 0.1% |

## Products per split

| Product | train | validation | test |
| --- | --- | --- | --- |
| Debt collection | 168,560 | 11,110 | 10,153 |
| Checking or savings account | 113,861 | 7,213 | 8,329 |
| Credit card | 105,689 | 6,900 | 7,586 |
| Money transfer, virtual currency, or money service | 62,030 | 3,475 | 3,535 |
| Credit reporting or other personal consumer reports | 48,079 | 770 | 913 |
| Mortgage | 43,143 | 2,651 | 3,012 |
| Vehicle loan or lease | 29,025 | 2,058 | 2,152 |
| Student loan | 26,618 | 1,463 | 1,434 |
| Payday loan, title loan, personal loan, or advance loan | 18,974 | 1,445 | 1,690 |
| Prepaid card | 11,295 | 431 | 561 |
| Debt or credit management | 5,468 | 387 | 381 |

## Checks

| Check | Result | Failing | Detail |
| --- | --- | --- | --- |
| Each complaint in exactly one split | Pass | 0 |  |
| No text shared between splits (no leakage) | Pass | 0 |  |
| Every split has data | Pass | 0 |  |
| All 11 products present in train | Pass | 0 |  |
| Splits are in time order (train < validation < test) | Pass | 0 |  |
| Credit reporting in train at most 50,000 | Pass | 0 |  |
| No narrative under 3 words | Pass | 0 |  |

## Analytics tables

| Table | Rows |
| --- | --- |
| monthly_product_issue | 5,411 |
| monthly_company_product | 90,974 |
