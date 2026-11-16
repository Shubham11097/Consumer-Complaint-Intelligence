# Consumer Complaint Intelligence

An open-source NLP system that reads consumer complaints about banks and financial products, classifies what each one is about, explains why, and flags issues that are suddenly growing.

> **Status:** Bronze, silver and gold layers built on 45 months of data (see [Data findings](#data-findings)). Baseline model next.

## The problem

Banks and regulators receive thousands of written complaints. Reading and routing them by hand is slow, and new problems (a fee change, a broken app feature) are spotted late. Any automated system must also explain its decisions, because financial services are heavily regulated.

## What this project does

1. **Classifies** each complaint by product and issue from its text.
2. **Explains** each prediction by showing which words drove it.
3. **Flags** complaint types that are rising faster than normal.
4. **Reports** trends and alerts in a Power BI dashboard.

## Data

Two sources from the [CFPB Consumer Complaint Database](https://www.consumerfinance.gov/data-research/consumer-complaints/):

- **Narratives archive** (monthly files, December 2011 to August 2026): includes the complaint text, published only where the consumer gave consent. Used for modelling.
- **Live database download** (18.9 million complaints, December 2011 to November 2026): no complaint text, as the CFPB no longer publishes narratives in the live data. Used for trend analysis.

## How the data flows (ELT, medallion layers)

| Layer | Contents | Status |
| --- | --- | --- |
| Bronze | Raw CFPB files exactly as downloaded, with checksums, one folder per source | Done |
| Silver | Complaints with narratives: typed, deduplicated, redactions replaced with placeholders, data-quality checked; Parquet | Done |
| Gold | Model data: one copy of each text, credit reporting capped in train, time-based train / validation / test splits, leakage checks. Analytics: monthly counts by product, issue and company (Parquet + CSV) | Done |

## Data findings

Profiled from bronze with `python -m src.profile_raw` and from silver with `python -m src.analyse_templates`. Full reports: [narratives profile](docs/data_profile_narratives.md) · [silver report](docs/silver_report.md) · [template analysis](docs/template_report.md) · [live database profile](docs/data_profile_live.md).

### Narratives archive (November 2022 – July 2026, 45 months)

| Measure | Value |
| --- | --- |
| Complaints in the 17 archive exports | 13,815,857 |
| Complaints with a written narrative | 2,711,934 (19.6%) |
| Written to silver after cleaning | 2,710,927 |
| Duplicate complaint IDs, unreadable dates, missing columns | None |
| Complaints mapped from pre-August-2023 category names | 302,054 |

**1. About 37% of narratives are copy-paste template letters.** 19,295 distinct texts each appear 5 or more times, covering 1,002,550 complaints. Just 132 texts account for 449,398 complaints; the most common appears 30,112 times. The top templates cite the Fair Credit Reporting Act ("15 U.S. Code 1681"), use legal phrases such as "estoppel by silence", or ask for accounts to be deleted. 90% of template complaints are about credit reporting (907,170 of 1,002,550). An independent analysis describes the same pattern ([Frank on Fraud](https://frankonfraud.com/?p=28987)).

**2. The template wave built up over two years, then stopped in January 2026.** Template letters made up 17% of narratives in November 2022, about 30% by mid-2023, and 40–47% from April 2024 to December 2025. In January 2026 the share fell to 9%, and it stayed between 7% and 11% through July 2026.

**3. Credit reporting narratives collapsed at the same time.** Credit reporting is 1,944,099 of the 2,710,927 silver narratives (72%). It grew from about 30,000 a month in late 2023 to 85,000–101,000 a month in 2025, then fell from 38,876 in December 2025 to 862 in January 2026, a drop of about 98%. Total complaints kept rising, and most other products held steady. The fall coincides with the end of the template wave; the cause is not yet known.

**4. A Cash App template drove a money-transfer spike in January 2025.** Money-transfer narratives jumped from 1,149 in December 2024 to 41,618 in January 2025, then fell back to 4,640 in February. A template complaint against Cash App first appears that month and is used 9,998 times overall. 26% of all money-transfer narratives are templates.

**5. The share of complaints published with a narrative fell every year:** 41% in 2022, 38% in 2023, 30% in 2024, 23% in 2025 and 3% in 2026. The CFPB stopped publishing narratives on 14 August 2026 and moved published narratives to its FOIA reading room ([Mondaq](https://www.mondaq.com/cfpb-stops-publishing-consumer-complaint-narratives-and-visualizations/1833726)).

**6. The CFPB reorganised its categories in August 2023.** Silver maps the old names onto the current 11 products, using the sub-product to split "Credit card or prepaid card" and to move credit repair into "Debt or credit management". Originals are kept in `product_original` and `issue_original`. See [`src/category_mapping.py`](src/category_mapping.py).

**7. Narratives are mostly short to medium.** 100–199 words is the most common length (810,766 complaints); 530,271 (20%) are under 50 words; 137,149 (5%) are over 500 words and will be truncated by a 512-token transformer.

### Live database (December 2011 – November 2026)

18,935,791 complaints with no narrative column: the live download no longer includes complaint text, so it is used only for trend analysis. Annual volume grew from 800,245 in 2022 to 6,253,441 in 2026 (to 5 November).

### What this means for modelling (planned)

- **Leakage:** if the same letter appears in training and test data, the model memorises it and its score is inflated. Keeping one copy of every exact text leaves 1,454,276 unique complaints.
- **Data drift:** training on everything would teach the model mostly "credit reporting template letter", while 2026 complaints look very different.
- **Plan:** keep one copy of each text (the earliest), drop narratives under 3 words, cap credit reporting at a fixed number sampled evenly across months, and split by time: train on November 2022 – February 2026, validate on March – April 2026, test on May – July 2026.

## Run it locally

Requires Python 3.10+.

```bash
python -m venv .venv
.venv\Scripts\activate          # Windows  (macOS/Linux: source .venv/bin/activate)
pip install -r requirements.txt

# 1. Put downloaded CFPB files (.zip/.csv/.json) in data/landing/
# 2. Store them untouched in the bronze layer, labelled by source
python -m src.ingest_bronze --source narratives   # monthly narratives archive files
python -m src.ingest_bronze --source live         # full live-database download
# 3. Profile the raw data -> docs/data_profile_<source>.md
python -m src.profile_raw --source narratives
# 4. Build the silver layer (cleaned Parquet) -> docs/silver_report.md
python -m src.build_silver
# 5. Analyse repeated template texts -> docs/template_report.md
python -m src.analyse_templates
# 6. Build the gold layer (model data + analytics tables) -> docs/gold_report.md
python -m src.build_gold
# 7. Run the tests
python -m pytest
```

## Project structure

```
src/            pipeline code
tests/          pytest tests
docs/           data profile, test strategy
data/           landing / bronze / silver / gold (not committed to Git)
```

## Roadmap

- [x] Bronze ingestion with checksums and manifest
- [x] Raw data profiling, including monthly category-change detection
- [x] Silver cleaning with data-quality checks
- [ ] Great Expectations data checks
- [x] Gold layer: deduplicated, capped, time-split model data and analytics tables
- [ ] Baseline classifier (TF-IDF + logistic regression)
- [ ] Transformer classifier (DistilRoBERTa) and SHAP explanations
- [ ] Emerging-issue detection
- [ ] Azure deployment (Data Lake Gen2, Data Factory, PostgreSQL) with Terraform
- [ ] CI/CD with GitHub Actions (dev → prod)
- [ ] Power BI dashboard

## Licence

MIT
