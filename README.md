# Consumer Complaint Intelligence

An open-source NLP system that reads consumer complaints about banks and financial products, classifies what each one is about, explains why, and flags issues that are suddenly growing.

> **Status:** Week 1 – raw data ingestion and profiling. Work in progress.

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
- [x] Raw data profiling
- [ ] Silver cleaning and Great Expectations checks
- [ ] Baseline classifier (TF-IDF + logistic regression)
- [ ] Transformer classifier (DistilRoBERTa) and SHAP explanations
- [ ] Emerging-issue detection
- [ ] Azure deployment (Data Lake Gen2, Data Factory, PostgreSQL) with Terraform
- [ ] CI/CD with GitHub Actions (dev → prod)
- [ ] Power BI dashboard

## Licence

MIT
