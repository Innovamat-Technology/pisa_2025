"""Step 11. Groups defined by thresholds that are identical in both cycles, and students without ESCS.

A. mean score and share of fixed groups (parental education, occupation, books, no valid ESCS); the
   share of a group is taken among the students with a valid value of the variable that defines it
B. change in the top-minus-bottom gap under six fixed rules, with the number of systems where it narrows
The rules do not depend on how ties are split into quartiles, which matters for parental education,
where half of the students sit at the maximum. All figures are for the 36 systems of the analysis
sample; the books rule is also given with Costa Rica, which has book data in both cycles.
(The complete-case version of the quartile analysis is in step 5, rows escs_cc / escs_h_cc.)
Usage: python scripts/11_missing_and_thresholds.py [math|read|scie]
"""
import sys

import numpy as np
import pandas as pd

from lib import brr
from lib import config as C
from lib.io_utils import load_base
from lib.stats import wmean

DOM = sys.argv[1] if len(sys.argv) > 1 else "math"
PVc = [f"pv{i}{DOM}" for i in range(1, 11)]
d = load_base(["wave", "cnt", "w_fstuwt", "escs", "hisei", "paredint", "books7", "cpos"] + PVc, all_rows=True)
W_ALL = np.load(C.INTERIM / "base_weights.npy")
c_lo, c_hi = d.cpos.quantile([.25, .75])          # fixed cuts over the pooled file, not re-anchored by cycle

GROUPS = {"Parents with tertiary education (16 years)": lambda g: g.paredint >= 16,
          "Parents with 12 years or fewer": lambda g: g.paredint <= 12,
          "HISEI >= 60": lambda g: g.hisei >= 60, "HISEI < 35": lambda g: g.hisei < 35,
          "More than 100 books": lambda g: g.books7 >= 5, "25 books or fewer": lambda g: g.books7 <= 3,
          "No valid ESCS": lambda g: g.escs.isna(), "Valid ESCS": lambda g: g.escs.notna()}
BASE_VAR = {"Parents with tertiary education (16 years)": "paredint", "Parents with 12 years or fewer": "paredint",
            "HISEI >= 60": "hisei", "HISEI < 35": "hisei", "More than 100 books": "books7", "25 books or fewer": "books7"}
RULES = {"Occupation: HISEI >= 60 vs < 35": (lambda g: g.hisei >= 60, lambda g: g.hisei < 35),
         "Education: tertiary vs 12 years or fewer": (lambda g: g.paredint >= 16, lambda g: g.paredint <= 12),
         "Books: more than 100 vs 25 or fewer": (lambda g: g.books7 >= 5, lambda g: g.books7 <= 3),
         "Possessions: top vs bottom quartile of the fixed 16-item score": (lambda g: g.cpos >= c_hi, lambda g: g.cpos <= c_lo),
         "Occupation and books": (lambda g: (g.hisei >= 60) & (g.books7 >= 5), lambda g: (g.hisei < 35) & (g.books7 <= 3)),
         "Occupation, education and books": (lambda g: (g.hisei >= 60) & (g.paredint >= 16) & (g.books7 >= 5),
                                             lambda g: (g.hisei < 35) & (g.paredint <= 12) & (g.books7 <= 3))}

TH, TR, share = {}, {}, []
for (cnt, wave), g in d.groupby(["cnt", "wave"], sort=True):
    pos = g.index.to_numpy()
    W, PV = W_ALL[pos], g[PVc].to_numpy("float64")
    ok = np.isfinite(PV).all(axis=1)
    for name, f in GROUPS.items():
        s = f(g).fillna(False).to_numpy()
        base = g[BASE_VAR[name]].notna().to_numpy() if name in BASE_VAR else np.ones(len(g), bool)
        share.append(dict(cnt=cnt, wave=wave, group=name, pct=wmean(s[base].astype(float), g.w_fstuwt.to_numpy()[base]) * 100))
        if (s & ok).sum() >= 30:
            TH[(name, wave, cnt)] = brr.theta_groups(np.zeros((s & ok).sum(), int), W[s & ok], PV[s & ok], 1)
    for name, (top, bottom) in RULES.items():
        code = np.where(top(g).to_numpy(), 1, np.where(bottom(g).to_numpy(), 0, -1))
        m = ok & (code >= 0)
        if (code[m] == 0).sum() >= 30 and (code[m] == 1).sum() >= 30:
            TR[(name, wave, cnt)] = brr.theta_groups(code[m], W[m], PV[m], 2)
share = pd.DataFrame(share)


def both_cycles(T, name, with_excluded):
    c = {k[2] for k in T if k[0] == name and (name, 2022, k[2]) in T and (name, 2025, k[2]) in T}
    return sorted(c if with_excluded else c - set(C.EXCLUDE))


rows = []
for name in GROUPS:
    cnts = both_cycles(TH, name, False)
    a = np.mean([TH[(name, 2022, c)] for c in cnts], axis=0)
    b = np.mean([TH[(name, 2025, c)] for c in cnts], axis=0)
    (e22, s22), (e25, s25) = brr.summarise(a), brr.summarise(b)
    sh = share[(share.group == name) & ~share.cnt.isin(C.EXCLUDE)].groupby("wave").pct.mean()
    rows.append(dict(group=name, n_systems=len(cnts), pct_2022=sh[2022], pct_2025=sh[2025], mean_2022=e22[0],
                     mean_2025=e25[0], change=e25[0] - e22[0], se=float(np.hypot(s22[0], s25[0]))))
t = pd.DataFrame(rows)
t.to_csv(C.TABLES / f"fixed_groups_{DOM}.csv", index=False)
print(f"=== {DOM}: fixed groups ===\n", t.round(2).to_string(index=False))

rows, per = [], []
for name in RULES:
    for with_excluded in (False, True):
        cnts = both_cycles(TR, name, with_excluded)
        if with_excluded and len(cnts) == len(both_cycles(TR, name, False)):
            continue
        ch = []
        for c in cnts:
            (g22, s22), (g25, s25) = brr.contrast(TR[(name, 2022, c)], [-1, 1]), brr.contrast(TR[(name, 2025, c)], [-1, 1])
            ch.append(g25 - g22)
            if not with_excluded:
                per.append(dict(rule=name, cnt=c, gap_2022=g22, gap_2025=g25, change=g25 - g22, se=float(np.hypot(s22, s25))))
        a = np.mean([TR[(name, 2022, c)] for c in cnts], axis=0)
        b = np.mean([TR[(name, 2025, c)] for c in cnts], axis=0)
        (g22, s22), (g25, s25) = brr.contrast(a, [-1, 1]), brr.contrast(b, [-1, 1])
        rows.append(dict(rule=name + (f" (with {', '.join(C.EXCLUDE)})" if with_excluded else ""), n_systems=len(cnts),
                         gap_2022=g22, gap_2025=g25, change=g25 - g22, se=float(np.hypot(s22, s25)),
                         narrows_in=int((np.array(ch) < 0).sum())))
r = pd.DataFrame(rows)
r.to_csv(C.TABLES / f"fixed_rules_{DOM}.csv", index=False)
pd.DataFrame(per).to_csv(C.TABLES / f"fixed_rules_by_system_{DOM}.csv", index=False)
print(f"\n=== {DOM}: top-minus-bottom gap under fixed rules ===\n", r.round(2).to_string(index=False))
