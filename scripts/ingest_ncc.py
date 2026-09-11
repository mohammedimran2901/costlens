#!/usr/bin/env python3
"""Ingest NHS National Cost Collection organisation-level source data (2020/21 - 2024/25).

Produces:
  data/ncc.db          SQLite master: year, org, dept, service, currency, activity,
                       actual_cost, expected_cost, national_mean, mff_scaled
  data/national_trend.json   per currency: unit-cost + activity trend across years
  data/org_annual.csv        tidy org x currency x year unit-cost table
  data/QC.md                 per-year coverage report

Usage: python3 scripts/ingest_ncc.py
Rules: no number ships without a source file in source-data/; suppressed cells (`*`) excluded.
"""
import csv, json, os, sqlite3

ROOT = os.path.join(os.path.dirname(__file__), "..")
SRC_EXTRACTED = os.path.join(ROOT, "source-data", "extracted")
DATA = os.path.join(ROOT, "data")
os.makedirs(DATA, exist_ok=True)

# year -> (unadjusted csv, mff-adjusted csv) relative to extracted/
FILES = {
    "2024/25": (
        "NCC_FY2024-25_Org_File1/NCC_FY2024-25_Org_File1.csv",
        "NCC_FY2024-25_Org_File2/NCC_FY2024-25_Org_File2.csv",
    ),
    "2023/24": (
        "Organisation_level_source_data_1_2324/Organisation_level_source_data_1_2324 v2.csv",
        "Organisation_level_source_data_2_2324/Organisation_level_source_data_2_2324 v2.csv",
    ),
    "2022/23": (
        "Organisation_level_source_data_1_2223/Organisation_level_source_data_1_2223 v2.csv",
        "Organisation_level_source_data_2_2223/Organisation_level_source_data_2_2223 v2.csv",
    ),
    "2021/22": (
        "Organisation_level_source_data_1_2122/Organisation_level_source_data_1_2122 v3.csv",
        "Organisation_level_source_data_2_2122/Organisation_level_source_data_2_2122 v3.csv",
    ),
    "2020/21": (
        "Organisation_level_source_data_1_2021/Organisation_level_source_data_1_2021 v2.csv",
        "Organisation_level_source_data_2_2021/Organisation_level_source_data_2_2021 v2.csv",
    ),
}

CANON = {
    "org": ["provider code", "org code"],
    "dept": ["department code", "dept code"],
    "service": ["service code"],
    "currency": ["currency code", "currency"],
    "activity": ["activity", "total activity"],
    "cost": ["actual cost"],
    "mffcost": ["mffd actual cost"],
    "expected": ["expected cost"],
    "national": ["national mean", "mffd national mean", "national_mean"],
    "mff": ["scaled mff"],
}

def sniff(path):
    with open(path, "r", encoding="utf-8-sig") as f:
        first = f.readline()
    return "\t" if first.count("\t") > first.count(",") else ","

def header_map(header):
    m = {}
    for i, h in enumerate(header):
        k = h.strip().lower()
        for canon, aliases in CANON.items():
            if k in aliases and canon not in m:
                m[canon] = i
    return m

def num(x):
    if x is None:
        return None
    x = x.strip() if isinstance(x, str) else x
    if x in ("", "*"):
        return None
    try:
        return float(x)
    except (ValueError, TypeError):
        return None


def ingest_year(year, db):
    unadj_rel, mff_rel = FILES[year]
    unadj_path = os.path.join(SRC_EXTRACTED, unadj_rel)
    mff_path = os.path.join(SRC_EXTRACTED, mff_rel)
    if not os.path.exists(unadj_path):
        print(f"[{year}] MISSING {unadj_rel}; skipped")
        return None
    delim = sniff(unadj_path)
    with open(unadj_path, newline="", encoding="utf-8-sig") as fu, \
         open(mff_path, newline="", encoding="utf-8-sig") as fm:
        ru = csv.reader(fu, delimiter=delim)
        rm = csv.reader(fm, delimiter=sniff(mff_path))
        hu, hm = header_map(next(ru)), header_map(next(rm))
        next(rm)
        missing = [k for k in ("org", "dept", "service", "currency", "activity", "cost", "national") if k not in hu]
        if missing:
            print(f"[{year}] header keys missing: {missing}; cols found: {list(hu)}")
        batch = []
        for r in ru:
            cur = r[hu["currency"]].strip()
            if cur in ("", "*"):
                continue
            batch.append((
                year, r[hu["org"]], r[hu["dept"]], r[hu["service"]], cur,
                num(r[hu["activity"]]), num(r[hu["cost"]]),
                num(r[hu["expected"]]) if "expected" in hu else None,
                num(r[hu["national"]]),
                num(r[hu["mff"]]) if "mff" in hu else None,
            ))
            if len(batch) >= 100000:
                db.executemany("INSERT INTO ncc VALUES (?,?,?,?,?,?,?,?,?,?)", batch)
                batch = []
        if batch:
            db.executemany("INSERT INTO ncc VALUES (?,?,?,?,?,?,?,?,?,?)", batch)
    rows = db.execute("SELECT COUNT(*) FROM ncc WHERE year=?", (year,)).fetchone()[0]
    currencies = db.execute("SELECT COUNT(DISTINCT currency) FROM ncc WHERE year=?", (year,)).fetchone()[0]
    orgs = db.execute("SELECT COUNT(DISTINCT org) FROM ncc WHERE year=?", (year,)).fetchone()[0]
    print(f"[{year}] rows={rows:,} currencies={currencies:,} orgs={orgs:,}")
    return dict(year=year, rows=rows, currencies=currencies, orgs=orgs)

def main():
    db_path = os.path.join(DATA, "ncc.db")
    if os.path.exists(db_path):
        os.remove(db_path)
    db = sqlite3.connect(db_path)
    db.execute(
        """CREATE TABLE ncc (
        year TEXT, org TEXT, dept TEXT, service TEXT, currency TEXT,
        activity REAL, actual_cost REAL, expected_cost REAL, national_mean REAL, mff_scaled REAL)"""
    )
    qc = []
    for year in FILES:
        qc.append(ingest_year(year, db))
    db.execute("CREATE INDEX idx_ncc_org ON ncc(year, org, currency)")
    db.execute("CREATE INDEX idx_ncc_cur ON ncc(year, currency)")
    db.commit()

    # national trend per currency (activity-weighted unit cost = total cost / total activity)
    trend = {}
    for year, currency, act, cost in db.execute(
        """SELECT year, currency, SUM(activity), SUM(actual_cost) FROM ncc
           WHERE activity IS NOT NULL AND actual_cost IS NOT NULL
           GROUP BY year, currency"""
    ):
        if act and act > 0:
            trend.setdefault(currency, {})[year] = {"unit_cost": round(cost / act, 2), "activity": int(act)}
    with open(os.path.join(DATA, "national_trend.json"), "w") as f:
        json.dump(trend, f, separators=(",", ":"))

    # org annual unit costs (tidy CSV)
    with open(os.path.join(DATA, "org_annual.csv"), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["year", "org", "dept", "service", "currency", "activity", "actual_cost", "unit_cost", "national_mean"])
        for row in db.execute(
            """SELECT year, org, dept, service, currency, activity, actual_cost,
                      ROUND(actual_cost/activity, 2), national_mean FROM ncc
               WHERE activity > 0 AND actual_cost IS NOT NULL"""
        ):
            w.writerow(row)

    with open(os.path.join(DATA, "QC.md"), "w") as f:
        f.write("# Ingestion QC — NHS NCC organisation-level data\n\n")
        f.write("| Year | Rows | Currencies | Orgs |\n|---|---|---|---|\n")
        for q in qc:
            if q:
                f.write(f"| {q['year']} | {q['rows']:,} | {q['currencies']:,} | {q['orgs']:,} |\n")
        f.write("\nSource: NHS England National Cost Collection organisation-level source data (unadjusted File 1), downloaded 2026-09-10. Suppressed cells (`*`) excluded from derived metrics.\n")

    n = db.execute("SELECT COUNT(*) FROM ncc").fetchone()[0]
    print(f"TOTAL rows in master: {n:,}")
    db.close()
    print("Done -> data/ncc.db, data/national_trend.json, data/org_annual.csv, data/QC.md")

if __name__ == "__main__":
    main()
