#!/usr/bin/env python3
"""Assemble all CostLens HTML pages from templates + data JSONs."""
import json, os, shutil
ROOT = os.path.join(os.path.dirname(__file__), '..')
T = os.path.join(ROOT, 'scripts')
D = os.path.join(ROOT, 'data')
DD = json.load(open(os.path.join(D, 'descriptions.json')))
NAMES = DD['orgs']; CUR = DD['currencies']

def build(tpl, out, reps):
    h = open(os.path.join(T, tpl)).read()
    for k, v in reps.items():
        h = h.replace(k, v)
    open(os.path.join(ROOT, out), 'w').write(h)
    print(out, len(h)//1024, 'KB')

def descs_for(codes):
    d = {}
    for c in codes:
        ds = CUR.get(c, {})
        d[c] = ds.get('2024/25') or ds.get('2023/24') or (sorted(ds.values())[-1] if ds else c)
    return d

# home
build('home_template.html', 'index.html', {})

# reference (search tool)
trend = json.load(open(os.path.join(D, 'national_trend.json')))
out = {'trend': trend, 'desc': descs_for(list(trend))}
build('reference_template.html', 'reference.html', {'/*__DATA__*/{}': json.dumps(out, separators=(',', ':'))})

# benchmark
B = json.load(open(os.path.join(D, 'org_bench.json')))
P = json.load(open(os.path.join(D, 'national_percentiles.json')))
codes = sorted({c for org in B for c in B[org]})
build('benchmark_template.html', 'benchmark.html', {
    '/*__BENCH__*/{}': json.dumps(B, separators=(',', ':')),
    '/*__PCTL__*/{}': json.dumps(P, separators=(',', ':')),
    '/*__NAMES__*/{}': json.dumps(NAMES, separators=(',', ':')),
    '/*__DESCS__*/{}': json.dumps(descs_for(codes), separators=(',', ':'))})

# drivers
DEC = json.load(open(os.path.join(D, 'decomposition.json')))
codes = sorted({c for org in DEC for c in DEC[org]})
build('drivers_template.html', 'drivers.html', {
    '/*__DECOMP__*/{}': json.dumps(DEC, separators=(',', ':')),
    '/*__NAMES__*/{}': json.dumps(NAMES, separators=(',', ':')),
    '/*__DESCS__*/{}': json.dumps(descs_for(codes), separators=(',', ':'))})

# cfo
CFO = json.load(open(os.path.join(D, 'cfo.json')))
codes = sorted({r['c'] for org in CFO['orgs'].values() for r in org['concerns'] + org['peers']})
build('cfo_template.html', 'cfo.html', {
    '/*__CFO__*/{}': json.dumps(CFO, separators=(',', ':')),
    '/*__NAMES__*/{}': json.dumps(NAMES, separators=(',', ':')),
    '/*__DESCS__*/{}': json.dumps(descs_for(codes), separators=(',', ':'))})

# accountant
build('accountant_template.html', 'accountant.html', {
    '/*__DECOMP__*/{}': json.dumps(DEC, separators=(',', ':')),
    '/*__PCTL__*/{}': json.dumps(P, separators=(',', ':')),
    '/*__NAMES__*/{}': json.dumps(NAMES, separators=(',', ':')),
    '/*__DESCS__*/{}': json.dumps(descs_for(codes), separators=(',', ':'))})

# remove old standalone index (reference now lives in reference.html)
old = os.path.join(ROOT, 'index.html.bak')
print('done')
