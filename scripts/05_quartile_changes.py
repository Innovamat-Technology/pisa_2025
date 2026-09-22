"""Step 5. Change 2022 -> 2025 in mean performance by equal-weight quartile of each index.

Quartiles are recomputed within country, cycle and replicate weight. Produces Table 2,
the country annexes, the decile profile, the quartile-size check and the complete-case rows.
Usage: python scripts/05_quartile_changes.py [math|read|scie]
"""
import itertools
import sys

import numpy as np
import pandas as pd

from lib import brr
from lib import config as C
from lib.io_utils import load_base, load_table

DOM = sys.argv[1] if len(sys.argv) > 1 else "math"
INDICES = ["escs", "escs_h", "escs_pca", "hisei_h", "pared_h", "homepos", "homepos_h", "books_h"]
PVc = [f"pv{i}{DOM}" for i in range(1, 11)]

d = load_base(["wave", "cnt", "escs", "hisei", "paredint", "homepos"] + PVc)
h = load_table("indices_h")
d = pd.concat([d, h.drop(columns=["wave", "cnt", "cntstuid"])], axis=1)
W_ALL = np.load(C.INTERIM / "base_weights.npy")
complete = d[["escs", "hisei", "paredint", "homepos", "homepos_h"]].notna().all(axis=1).to_numpy()

TH, TH10, check = {}, {}, []
for (cnt, wave), g in d.groupby(["cnt", "wave"], sort=True):
    pos = g.index.to_numpy()
    W, PV = W_ALL[pos], g[PVc].to_numpy("float64")
    ok = np.isfinite(PV).all(axis=1)
    for idx in INDICES + ["escs_cc", "escs_h_cc"]:
        var = idx.removesuffix("_cc")
        m = ok & g[var].notna().to_numpy()
        if idx.endswith("_cc"):
            m &= complete[pos]
        if m.sum() < 200:
            continue
        x = g[var].to_numpy("float64")[m]
        TH[(cnt, wave, idx)] = brr.theta_quartiles(x, W[m], PV[m])
        if idx in ("escs", "escs_h", "escs_pca", "homepos", "homepos_h") and m.sum() >= 400:
            TH10[(cnt, wave, idx)] = brr.theta_quartiles(x, W[m], PV[m], k=10)
        code, wf = brr.quartile_codes(x, W[m]), W[m][:, 0]
        row = dict(cnt=cnt, wave=wave, index=idx, n=int(m.sum()))
        for k in range(4):
            row[f"weight_Q{k + 1}"] = wf[code == k].sum() / wf.sum() * 100
            row[f"n_Q{k + 1}"] = int((code == k).sum())
        check.append(row)
pd.DataFrame(check).to_csv(C.TABLES / f"quartile_check_{DOM}.csv", index=False)

PAIRS = list(itertools.combinations(range(4), 2))
rows = []
for idx in INDICES + ["escs_cc", "escs_h_cc"]:
    cnts = sorted({k[0] for k in TH if k[2] == idx and (k[0], 2022, idx) in TH and (k[0], 2025, idx) in TH})
    for cnt in cnts + ["OECD"]:
        if cnt == "OECD":                                       # simple average, replicate by replicate
            a = np.mean([TH[(p, 2022, idx)] for p in cnts], axis=0)
            b = np.mean([TH[(p, 2025, idx)] for p in cnts], axis=0)
        else:
            a, b = TH[(cnt, 2022, idx)], TH[(cnt, 2025, idx)]
        (e22, s22), (e25, s25) = brr.summarise(a), brr.summarise(b)
        r = dict(index=idx, cnt=cnt, n_systems=len(cnts))
        for k in range(4):
            r[f"Q{k + 1}_2022"], r[f"Q{k + 1}_2025"] = e22[k], e25[k]
            r[f"Q{k + 1}_change"], r[f"Q{k + 1}_se"] = e25[k] - e22[k], float(np.hypot(s22[k], s25[k]))
        for i, j in PAIRS:
            c = np.zeros(4)
            c[j], c[i] = 1, -1
            (g22, t22), (g25, t25) = brr.contrast(a, c), brr.contrast(b, c)
            nm = f"Q{j + 1}-Q{i + 1}"
            r[f"{nm}_2022"], r[f"{nm}_2025"] = g22, g25
            r[f"{nm}_change"], r[f"{nm}_se"] = g25 - g22, float(np.hypot(t22, t25))
        rows.append(r)
t = pd.DataFrame(rows)
t.to_csv(C.TABLES / f"quartiles_{DOM}.csv", index=False)

# deciles (OECD average only)
rows = []
for idx in sorted({k[2] for k in TH10}):
    cnts = sorted({k[0] for k in TH10 if k[2] == idx})
    a = np.mean([TH10[(p, 2022, idx)] for p in cnts], axis=0)
    b = np.mean([TH10[(p, 2025, idx)] for p in cnts], axis=0)
    (e22, s22), (e25, s25) = brr.summarise(a), brr.summarise(b)
    for k in range(10):
        rows.append(dict(index=idx, decile=k + 1, n_systems=len(cnts), mean_2022=e22[k], mean_2025=e25[k],
                         change=e25[k] - e22[k], se=float(np.hypot(s22[k], s25[k]))))
    (g22, t22), (g25, t25) = brr.contrast(a, [-1] + [0] * 8 + [1]), brr.contrast(b, [-1] + [0] * 8 + [1])
    rows.append(dict(index=idx, decile="D10-D1", n_systems=len(cnts), mean_2022=g22, mean_2025=g25,
                     change=g25 - g22, se=float(np.hypot(t22, t25))))
pd.DataFrame(rows).to_csv(C.TABLES / f"deciles_{DOM}.csv", index=False)

o = t[t.cnt == "OECD"].set_index("index")
cols = [f"Q{k}_change" for k in range(1, 5)] + ["Q4-Q1_change", "Q4-Q1_se", "n_systems"]
print(f"=== {DOM}: change 2022 -> 2025, simple OECD average ===")
print(o[cols].round(2).to_string())
c = t[t.cnt != "OECD"]
for idx in ("escs", "escs_h", "escs_pca"):
    x = c[c["index"] == idx]
    z = x["Q4-Q1_change"] / x["Q4-Q1_se"]
    print(f"{idx}: significant narrowing (z < -1.96) in {int((z < -1.96).sum())} systems:",
          ", ".join(x.cnt[z < -1.96]))
ch = pd.DataFrame(check)
dev = (ch[[f"weight_Q{k}" for k in range(1, 5)]] - 25).abs().to_numpy().max()
print(f"largest deviation of a quartile from 25% of the weight: {dev:.3f} pp; "
      f"smallest quartile: {int(ch[[f'n_Q{k}' for k in range(1, 5)]].to_numpy().min())} students")
