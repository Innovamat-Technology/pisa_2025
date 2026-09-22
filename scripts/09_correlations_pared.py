"""Step 9. Within-system correlations between the components and with achievement, implied weights of the
published ESCS, and the coverage, distribution and non-response of parental education.
Usage: python scripts/09_correlations_pared.py [math|read|scie]"""
import sys

import numpy as np
import pandas as pd

from lib import config as C
from lib.io_utils import load_base, load_table
from lib.stats import wcorr, wmean

DOM = sys.argv[1] if len(sys.argv) > 1 else "math"
PVc = [f"pv{i}{DOM}" for i in range(1, 11)]
d = load_base(["wave", "cnt", "w_fstuwt", "escs", "hisei", "paredint", "homepos", "hisced"] + PVc)
d["score"] = d[PVc].mean(axis=1)
h = load_table("indices_h", ["hisei_h", "pared_h", "homepos_h"])
d = pd.concat([d, h], axis=1)


def corr_oecd(wave, a, b):
    return np.nanmean([wcorr(g[a], g[b], g.w_fstuwt) for _, g in d[d.wave == wave].groupby("cnt")])


rows = []
for tag, (H, P, M) in (("published", ("hisei", "paredint", "homepos")), ("harmonised", ("hisei_h", "pared_h", "homepos_h"))):
    for a, b, name in ((H, P, "HISEI - PARED"), (H, M, "HISEI - HOMEPOS"), (P, M, "PARED - HOMEPOS"),
                       (H, "score", "HISEI - achievement"), (P, "score", "PARED - achievement"),
                       (M, "score", "HOMEPOS - achievement")):
        r22, r25 = corr_oecd(2022, a, b), corr_oecd(2025, a, b)
        rows.append(dict(version=tag, pair=name, r_2022=r22, r_2025=r25, change=r25 - r22))
t9 = pd.DataFrame(rows)
t9.to_csv(C.TABLES / f"correlations_{DOM}.csv", index=False)
print(f"=== {DOM}: correlations ===\n", t9.round(3).to_string(index=False))

rows = []
for wave in (2022, 2025):
    g = d[d.wave == wave].dropna(subset=["escs", "hisei", "paredint", "homepos"])
    w = g.w_fstuwt.to_numpy()
    X = g[["hisei", "paredint", "homepos"]].to_numpy("float64")
    mu = np.average(X, axis=0, weights=w)
    Xz = np.column_stack([np.ones(len(g)), (X - mu) / np.sqrt(np.average((X - mu) ** 2, axis=0, weights=w))])
    y = g.escs.to_numpy("float64")
    b = np.linalg.lstsq(Xz * np.sqrt(w)[:, None], y * np.sqrt(w), rcond=None)[0]
    r2 = 1 - np.average((y - Xz @ b) ** 2, weights=w) / np.average((y - np.average(y, weights=w)) ** 2, weights=w)
    rows.append(dict(wave=wave, hisei=b[1], pared=b[2], homepos=b[3], r2=r2, n=len(g)))
ti = pd.DataFrame(rows)
ti.to_csv(C.TABLES / "escs_implied_weights.csv", index=False)
print("\n=== Implied weights of the published ESCS (students with the three components observed) ===")
print(ti.round(3).to_string(index=False))

print("\n=== PARED: coverage, distribution and non-response ===")
rows = []
for wave in (2022, 2025):
    g = d[d.wave == wave]
    has, lacks = g[g.paredint.notna()], g[g.paredint.isna()]
    dist = has.groupby("paredint").w_fstuwt.sum() / has.w_fstuwt.sum() * 100
    hv = g[g.hisei.notna()].copy()
    hv["band"] = pd.cut(hv.hisei, [0, 35, 50, 65, 90], labels=["<35", "35-50", "50-65", "65+"])
    miss = hv.groupby("band", observed=True).apply(lambda x: wmean(x.paredint.isna().astype(float), x.w_fstuwt) * 100,
                                                   include_groups=False)
    r = dict(wave=wave,
             coverage_pooled=wmean(g.paredint.notna().astype(float), g.w_fstuwt) * 100,
             coverage_mean_of_systems=np.mean([wmean(x.paredint.notna().astype(float), x.w_fstuwt)
                                               for _, x in g.groupby("cnt")]) * 100,
             pct_at_maximum_pooled=dist.iloc[-1],
             hisei_if_pared_missing=wmean(lacks.hisei, lacks.w_fstuwt), hisei_if_pared_valid=wmean(has.hisei, has.w_fstuwt),
             score_if_pared_missing=wmean(lacks.score, lacks.w_fstuwt), score_if_pared_valid=wmean(has.score, has.w_fstuwt))
    r.update({f"pct_no_pared_hisei_{k}": v for k, v in miss.items()})
    rows.append(r)
    print(f"  {wave}: distribution of PARED (pooled, %):", dist.round(1).to_dict())
tp = pd.DataFrame(rows)
for c in ("hisei", "homepos", "escs"):
    tp[f"coverage_{c}_pooled"] = [wmean(d[d.wave == y][c].notna().astype(float), d[d.wave == y].w_fstuwt) * 100 for y in (2022, 2025)]
tp.to_csv(C.TABLES / f"pared_coverage_{DOM}.csv", index=False)
print(tp.round(1).T.to_string())
