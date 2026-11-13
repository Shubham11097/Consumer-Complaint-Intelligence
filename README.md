# Consumer Complaint Intelligence

An open-source NLP system that reads consumer complaints about banks and financial products, classifies what each one is about, explains why, and flags issues that are suddenly growing.

> **Status:** Week 1 complete – raw data ingested and profiled (see [Data findings](#data-findings)). Week 2: silver layer cleaning.

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
| Silver | Typed, deduplicated, standardised, cleaned text | Planned |
| Gold | Model-ready datasets and analytics tables | Planned |

## Data findings

Profiled from the bronze layer with `python -m src.profile_raw`. Full reports: [narratives archive](docs/data_profile_narratives.md) · [live database](docs/data_profile_live.md).

### Narratives archive (March 2025 – July 2026)

| Measure | Value |
| --- | --- |
| Complaints in the 11 monthly exports | 8,816,336 |
| Complaints with a written narrative | 1,078,038 (12.2%) |
| Duplicate complaint IDs, unreadable dates, missing columns | None |
| Products | 11, every one present in every month |

**1. Credit reporting narratives collapsed in January 2026.** Credit reporting accounts for 746,837 of the 1,078,038 narratives (69%). It ran at roughly 85,000 a month through most of 2025 (peak 101,415 in July 2025), fell to 38,876 in December 2025, then to 862 in January 2026, a drop of about 98% in one month. It stayed below 900 a month through July 2026. Total complaints kept rising over the same period, and the other 10 products held steady. The cause is not yet known.

**2. The share of complaints published with a narrative is falling.** It was 26.5% in March 2025 and 1.5% in July 2026. Most of the fall comes from credit reporting. Of the other products, debt collection fell the most, from about 9,000–10,000 a month in mid-2025 to about 5,000–6,000 in May–June 2026; most others stayed roughly flat.

**3. Categories are stable.** No product was renamed or added during the period. Only one issue with at least 50 complaints stops early ("Identity theft protection or other monitoring services", 246 complaints, last seen June 2026). The whole range can be used with one consistent set of labels.

**4. February and July 2026 are low for every product.** Narratives fall by 40–50% from the previous month in both cases, across all products, which points to incomplete exports rather than real changes. To be confirmed before these months are used for testing.

**5. Narratives are mostly short to medium.** 100–199 words is the most common length (305,729 complaints). 197,933 (18%) are under 50 words. 56,796 (5%) are over 500 words and will be truncated by a 512-token transformer.

### Live database (December 2011 – November 2026)

18,935,791 complaints with no narrative column: the live download no longer includes complaint text, so it is used only for trend analysis. Annual volume grew from 800,245 in 2022 to 6,253,441 in 2026 (to 5 November).

### What this means for modelling (planned)

- Training on all narratives would teach the model mostly "credit reporting", and the 2026 test months look very different from 2025. This is **data drift**.
- Plan: keep all 17 months, cap credit reporting at about 30,000 complaints sampled evenly across months (about 360,000 complaints in total), and split by time: train on March 2025 – February 2026, validate on March – April 2026, test on May – July 2026.

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
# 4. Run the tests
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
- [ ] Silver cleaning and Great Expectations checks
- [ ] Baseline classifier (TF-IDF + logistic regression)
- [ ] Transformer classifier (DistilRoBERTa) and SHAP explanations
- [ ] Emerging-issue detection
- [ ] Azure deployment (Data Lake Gen2, Data Factory, PostgreSQL) with Terraform
- [ ] CI/CD with GitHub Actions (dev → prod)
- [ ] Power BI dashboard

## Licence

MIT
