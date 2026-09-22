"""Step 10. Ten constructions of the harmonised composite (Table D.1).

1-5 apply the OECD aggregation (equal weights of the standardised components) with different
treatments of missing components and of the standardisation scope; 6-10 are principal-component
variants. Construction 1 is the paper's composite (escs_h of step 4).
Usage: python scripts/10_composite_weights.py [math|read|scie]
"""
import sys

import numpy as np
import pandas as pd

from lib import brr
from lib import config as C
from lib.escs_rule import escs
from lib.io_utils import load_base, load_table
from lib.stats import cell_weights

DOM = sys.argv[1] if len(sys.argv) > 1 else "math"
PVc = [f"pv{i}{DOM}" for i in range(1, 11)]
d = load_base(["wave", "cnt", "w_fstuwt", "hisei", "paredint"] + PVc)
d = pd.concat([d, load_table("indices_h", ["hisei_h", "pared_h", "homepos_h"])], axis=1)
d["homepos_grm"] = load_table("homepos_grm", ["homepos_grm"]).homepos_grm.to_numpy()[:len(d)]
w = cell_weights(d)
group = d.groupby(["cnt", "wave"], sort=False).ngroup().to_numpy()
RAW = np.column_stack([d.hisei.to_numpy("float64"), d.paredint.replace({3.0: 6.0, 14.5: 14.0}).to_numpy("float64"),
                       d.homepos_grm.to_numpy("float64")])
COMP = ["hisei_h", "pared_h", "homepos_h"]


def z(x, m):
    x = np.asarray(x, "float64")
    ok = np.isfinite(x) & m
    mu = np.average(x[ok], weights=w[ok])
    out = np.full(len(x), np.nan)
    out[m] = (x[m] - mu) / np.sqrt(np.average((x[ok] - mu) ** 2, weights=w[ok]))
    return out


def pca(X, m):
    n_valid, Xi = np.isfinite(X).sum(axis=1), np.nan_to_num(X)
    full = (n_valid == 3) & m
    _, vec = np.linalg.eigh(np.cov(Xi[full].T, aweights=w[full]))
    v = vec[:, -1] if vec[0, -1] > 0 else -vec[:, -1]
    s = np.where(n_valid >= 2, Xi @ v, np.nan)
    s[~m] = np.nan
    return s, v


every = np.ones(len(d), bool)
waves = {2022: (d.wave == 2022).to_numpy(), 2025: (d.wave == 2025).to_numpy()}
V = {}
V["1. OECD rule: equal-weighted mean, regression imputation (the paper's composite)"] = escs(RAW, group, w)[0]
V["2. OECD rule, mean of the available components"] = escs(RAW, group, w, imputation="mean")[0]
V["3. OECD rule, complete cases only"] = escs(RAW, group, w, imputation="complete")[0]
V["4. OECD rule, imputation without the random residual"] = escs(RAW, group, w, noise=False)[0]
s = np.full(len(d), np.nan)
for m in waves.values():
    sub = np.where(m)[0]
    s[sub] = escs(RAW[sub], group[sub], w[sub] / w[sub].sum() * len(sub))[0]
V["5. OECD rule, metric re-anchored in each cycle"] = s
Xp = np.column_stack([z(d[c], every) for c in COMP])
V["6. First principal component, pooled standardisation"] = pca(Xp, every)[0]
s = np.full(len(d), np.nan)
for y, m in waves.items():
    si, _ = pca(np.column_stack([z(d[c], m) for c in COMP]), m)
    s[m] = si[m]
V["7. Per-cycle standardisation, per-cycle principal component"] = s
s, vs = np.full(len(d), np.nan), {}
for y, m in waves.items():
    si, vs[y] = pca(Xp, m)
    s[m] = si[m]
V["8. Pooled standardisation, per-cycle principal component"] = s
n_valid = np.isfinite(Xp).sum(axis=1)
V["9. 2022 principal-component weights in both cycles"] = np.where(n_valid >= 2, np.nan_to_num(Xp) @ vs[2022], np.nan)
V["10. 2025 principal-component weights in both cycles"] = np.where(n_valid >= 2, np.nan_to_num(Xp) @ vs[2025], np.nan)

W_ALL = np.load(C.INTERIM / "base_weights.npy")
rows = []
for name, s in V.items():
    TH = {}
    for (cnt, wave), g in d.groupby(["cnt", "wave"], sort=True):
        pos = g.index.to_numpy()
        PV = g[PVc].to_numpy("float64")
        m = np.isfinite(PV).all(axis=1) & np.isfinite(s[pos])
        TH[(cnt, wave)] = brr.theta_quartiles(s[pos][m], W_ALL[pos][m], PV[m])
    cnts = sorted({c for c, _ in TH})
    a = np.mean([TH[(c, 2022)] for c in cnts], axis=0)
    b = np.mean([TH[(c, 2025)] for c in cnts], axis=0)
    (e22, _), (e25, _) = brr.summarise(a), brr.summarise(b)
    (g22, s22), (g25, s25) = brr.contrast(a, [-1, 0, 0, 1]), brr.contrast(b, [-1, 0, 0, 1])
    rows.append(dict(construction=name, Q1_change=e25[0] - e22[0], Q4_change=e25[3] - e22[3],
                     gap_change=g25 - g22, se=float(np.hypot(s22, s25)), coverage=float(np.isfinite(s).mean() * 100)))
    print(f"  {name:75s} Q1 {rows[-1]['Q1_change']:+5.1f}  Q4 {rows[-1]['Q4_change']:+5.1f}  "
          f"gap {rows[-1]['gap_change']:+5.2f} (se {rows[-1]['se']:.2f})", flush=True)
pd.DataFrame(rows).to_csv(C.TABLES / f"composite_weights_{DOM}.csv", index=False)
