# CostLens — NHS Costing Intelligence

Free HRG reference tool + (planned) predictive costing intelligence for UK NHS finance teams, built on **published NHS England National Cost Collection (NCC)** data.

## What exists today

- **`index.html`** — single-file, offline-capable **HRG currency reference tool**: search ~3,300 service currencies, see national average unit cost, activity and 5-year trend (2020/21→2024/25). Serve with `python3 -m http.server` or deploy as a static page.
- **`data/ncc.db`** — SQLite master table, **7,879,879 rows**: `year, org, dept, service, currency, activity, actual_cost, expected_cost, national_mean, mff_scaled` for ~210 trusts × 5 years.
- **`data/national_trend.json`** — national activity-weighted unit cost + activity per currency per year.
- **`data/org_annual.csv`** — tidy trust × currency × year unit-cost table (1.96M rows).
- **`data/descriptions.json`** — currency descriptions (per vintage) + organisation code→name.
- **`data/QC.md`** — per-year coverage report.

## Data pipeline

1. `source-data/` — official NHS England zips/xlsx (vintage-labelled, never edited):
   - 2024/25: `NCC_FY2024-25_Org_File1/2/3.zip`, `NCCI-2024_25.zip`, national schedule (in `drg-crosswalk/source-data/`)
   - 2020/21–2023/24: `Organisation_level_source_data_1/2/3_<year>.zip` + national schedules FY20-21, FY21-22
   - Downloads were bot-protected; fetched via headless browser (Playwright). To refresh: get new URLs from england.nhs.uk/costing-in-the-nhs/national-cost-collection
2. `scripts/ingest_ncc.py` — `python3 scripts/ingest_ncc.py` → rebuilds `data/` from `source-data/extracted/`
   - Unadjusted File 1 is the master; MFF-adjusted File 2 available for peer comparisons
   - Suppressed cells (`*`) excluded from derived metrics
   - Column drift across vintages handled by canonical header map (e.g. `National_Mean` in 2022/23)

## Data rules (same as drg-crosswalk)

1. No number ships without a source file in `source-data/`.
2. Suppression is respected — "insufficient submissions", never fabricated.
3. Vintage disclosed everywhere (source + download date in `data/QC.md`).

## Roadmap (paid tier)

- [ ] Trust selector benchmarking vs peer group (MFF-adjusted, Part 2 data)
- [ ] Decomposition engine: cost-per-case change split into price/inflation vs activity vs casemix vs efficiency
- [ ] Forecast next-year unit costs/activity per HRG (log-linear trend + national priors)
- [ ] CRES spreader: rank HRGs by gap-to-efficient-peer × volume × realism
- [ ] NCCI positioning (the NCCI zips are already downloaded)

**Disclaimer:** reference tool only; not affiliated with NHS England. Not for clinical or contractual decision-making without verification against official publications.
