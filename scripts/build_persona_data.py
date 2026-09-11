#!/usr/bin/env python3
"""Build CFO/accountant persona data: peer groups (by size), forecasts, concerns."""
import sqlite3, json, os
from statistics import quantiles
ROOT = os.path.join(os.path.dirname(__file__), '..')
db = sqlite3.connect(os.path.join(ROOT, 'data', 'ncc.db'))
years = ['2020/21','2021/22','2022/23','2023/24','2024/25']

# bulk load: org x currency x year aggregated
agg = {}
for org, cur, y, act, cost in db.execute("""SELECT org, currency, year, SUM(activity), SUM(actual_cost)
        FROM ncc WHERE activity>0 AND actual_cost IS NOT NULL GROUP BY org, currency, year"""):
    agg.setdefault(org, {}).setdefault(cur, {})[y] = (act, cost)

# national unit cost per currency-year
nat = {}
for y, c, act, cost in db.execute("""SELECT year, currency, SUM(activity), SUM(actual_cost) FROM ncc
        WHERE activity>0 AND actual_cost IS NOT NULL GROUP BY year, currency"""):
    if act: nat.setdefault(c, {})[y] = cost/act

sizes = {o: (db.execute("SELECT SUM(activity) FROM ncc WHERE year='2024/25' AND activity>0 AND org=?", (o,)).fetchone()[0] or 0) for o in agg}
vals = sorted(v for v in sizes.values() if v)
def quartile(v):
    for i, t in enumerate(quantiles(vals, n=4)):
        if v <= t: return ['Small','Mid','Large','Very large'][i]
    return 'Very large'
groups = {}
for o, s in sizes.items(): groups.setdefault(quartile(s), []).append(o)
for g in groups: groups[g].sort()

# peer medians per group/currency/year
peer_uc = {}
for g, members in groups.items():
    mset = set(members)
    acc = {}
    for org in members:
        for cur, yseries in agg.get(org, {}).items():
            for y, (a, c) in yseries.items():
                acc.setdefault(cur, {}).setdefault(y, [0.0, 0.0])
                acc[cur][y][0] += a; acc[cur][y][1] += c
    for cur, ym in acc.items():
        for y, (a, c) in ym.items():
            if a: peer_uc.setdefault(g, {}).setdefault(cur, {})[y] = c/a

def forecast(series):
    ys = [v for v in series if v is not None]
    if len(ys) < 3: return None, None
    n = len(ys); xs = list(range(n))
    mx = sum(xs)/n; my = sum(ys)/n
    b = sum((x-mx)*(y-my) for x,y in zip(xs,ys)) / sum((x-mx)**2 for x in xs)
    a = my - b*mx
    resid = [y-(a+b*x) for x,y in zip(xs,ys)]
    se = (sum(r*r for r in resid)/max(n-2,1))**0.5
    return a + b*n, se

cfo = {}
for g, members in groups.items():
    pu = peer_uc.get(g, {})
    for org in members:
        oagg = agg.get(org, {})
        cost_series, act_series = {}, {}
        for cur, ym in oagg.items():
            for y, (a, c) in ym.items():
                cost_series[y] = cost_series.get(y, 0) + c
                act_series[y] = act_series.get(y, 0) + a
        if len(cost_series) < 3: continue
        fc_cost, se_cost = forecast([cost_series.get(y) for y in years])
        concerns, peer_rows = [], []
        # rank lines by 2024/25 cost
        lines = sorted(oagg.items(), key=lambda kv: -(kv[1].get(years[-1], (0,0))[1]))[:80]
        for cur, ym in lines:
            my = {y: c/a for y, (a, c) in ym.items() if a and c}
            f, se = forecast([my.get(y) for y in years])
            if f is None: continue
            act1 = ym.get(years[-1], (0,0))[0]; cost1 = ym.get(years[-1], (0,0))[1]
            n0, n1 = nat.get(cur, {}).get(years[0]), nat.get(cur, {}).get(years[-1])
            own0, own1 = my.get(years[0]), my.get(years[-1])
            if n0 and n1 and own0 and own1:
                own_chg, nat_chg = own1/own0-1, n1/n0-1
                extra = (own_chg - nat_chg) * cost1
                if abs(extra) > 100000:
                    concerns.append({'c':cur,'extra':round(extra),'f':round(f,2),'se':round(se,2),
                                     'own':round(own_chg,3),'nat':round(nat_chg,3),'uc':round(own1,2),'act':int(act1)})
            pmed = pu.get(cur, {}).get(years[-1])
            if pmed and own1:
                peer_rows.append({'c':cur,'uc':round(own1,2),'peer':round(pmed,2),
                                  'gap':round(own1/pmed-1,3),'act':int(act1),'f':round(f,2)})
        cfo[org] = {'group':g, 'size':int(sizes[org]),
                    'cost':{y:round(cost_series[y]) for y in cost_series},
                    'act':{y:round(act_series[y]) for y in act_series},
                    'fc_cost':fc_cost and (round(fc_cost), round(se_cost)),
                    'concerns':sorted(concerns,key=lambda x:-abs(x['extra']))[:15],
                    'peers':sorted(peer_rows,key=lambda r:-r['act'])[:30]}
json.dump({'groups':groups,'orgs':cfo}, open(os.path.join(ROOT,'data','cfo.json'),'w'), separators=(',',':'))
print('orgs:', len(cfo), '| groups:', {k:len(v) for k,v in groups.items()})
r = cfo.get('R0A')
print('R0A:', r['group'], 'fc', r['fc_cost'], 'cost24', r['cost'].get('2024/25'), 'concerns', len(r['concerns']))
