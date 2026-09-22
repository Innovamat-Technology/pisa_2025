"""Step 8. Cultural capital versus living conditions: item-level evidence.

A. within-system correlation of every possessions item with achievement, with parental occupation and
   with parental education, and its partial correlation with achievement net of both
B. the twenty national items of 2025: share of "yes", systems administering, correlation
C. subscales of the 2022 items
D. what the published HOMEPOS adds beyond the 16 common items (residual analysis)
Usage: python scripts/08_items.py [math|read|scie]
"""
import sys

import numpy as np
import pandas as pd

from lib import config as C
from lib.io_utils import load_base, load_table
from lib.stats import equal_weight_quartile, wcorr, wmean, zscore

COMMON, BT, DROP, NAT = ([c.lower() for c in x] for x in (C.COMMON, C.BOOKTYPES, C.DROPPED_OTHER, C.NATIONAL))
DOM = sys.argv[1] if len(sys.argv) > 1 else "math"
PVc = [f"pv{i}{DOM}" for i in range(1, 11)]
d = load_base(["wave", "cnt", "w_fstuwt", "homepos", "hisei", "paredint", "n_booktypes", "n_national_yes"] + PVc + COMMON + BT + DROP + NAT)
d["score"] = d[PVc].mean(axis=1)          # mean of the ten plausible values, for description only
d = d.drop(columns=PVc)
d["homepos_h"] = load_table("indices_h", ["homepos_h"]).homepos_h.to_numpy()
w = d.w_fstuwt.to_numpy("float64")


def corr_oecd(wave, a, b="score"):
    r = np.array([wcorr(g[a], g[b], g.w_fstuwt) for _, g in d[d.wave == wave].groupby("cnt")])
    return np.nan if np.isnan(r).all() else np.nanmean(r)


# A ---------------------------------------------------------------------------------------------
def validate(wave, item):
    """On the students with the item, the score, HISEI and PARED all observed: correlation of the item with
    each of the three, and its partial correlation with the score net of HISEI and PARED; means over systems."""
    out = []
    for _, g in d[d.wave == wave].groupby("cnt"):
        g = g[[item, "score", "hisei", "paredint", "w_fstuwt"]].dropna()
        if len(g) < 100 or g[item].nunique() < 2:
            continue
        w = g.w_fstuwt.to_numpy()
        Z = np.column_stack([np.ones(len(g)), g.hisei, g.paredint]) * np.sqrt(w)[:, None]
        res = [v * np.sqrt(w) - Z @ np.linalg.lstsq(Z, v * np.sqrt(w), rcond=None)[0]
               for v in (g[item].to_numpy("float64"), g.score.to_numpy("float64"))]
        out.append([wcorr(g[item], g[v], w) for v in ("score", "hisei", "paredint")] + [np.corrcoef(res[0], res[1])[0, 1]])
    return dict(zip(["r_score_cc", "r_hisei", "r_pared", "partial_r"], np.nanmean(out, axis=0) if out else [np.nan] * 4))


rows = []
for c in COMMON + BT + DROP + NAT:
    group = "common" if c in COMMON else "2022 only" if c in BT + DROP else "2025 only"
    for wave in (2022, 2025):
        if (wave == 2022 and c in NAT) or (wave == 2025 and c in BT + DROP):
            continue
        rows.append(dict(item=c.upper(), label=C.LABELS[c.upper()], group=group, wave=wave,
                         r_score=corr_oecd(wave, c), **validate(wave, c)))
t = pd.DataFrame(rows).dropna(subset=["r_score"])
t.to_csv(C.TABLES / f"items_validation_{DOM}.csv", index=False)
COLS = ["r_score", "r_score_cc", "r_hisei", "r_pared", "partial_r"]
grp = t.groupby(["group", "wave"])[COLS].mean()
grp.insert(0, "n_items", t.groupby(["group", "wave"]).size())
grp.to_csv(C.TABLES / f"items_validation_groups_{DOM}.csv")
print(f"=== {DOM}: item validation, group means ===\n", grp.round(3).to_string())
print(t[["label", "group", "wave", "r_score", "r_score_cc", "r_hisei", "partial_r"]].round(3).to_string(index=False))

# B ---------------------------------------------------------------------------------------------
rows = []
for c in NAT:
    g = d[(d.wave == 2025) & d[c].notna()]
    pct = [wmean(x[c], x.w_fstuwt) * 100 for _, x in g.groupby("cnt") if len(x) >= 100]
    rows.append(dict(item=c.upper(), label=C.LABELS[c.upper()], pct_yes=np.mean(pct) if pct else np.nan,
                     n_systems=len(pct), r_score=corr_oecd(2025, c) if pct else np.nan))
t7 = pd.DataFrame(rows).sort_values("pct_yes", ascending=False)
t7.to_csv(C.TABLES / f"national_items_{DOM}.csv", index=False)
print("\n=== national items ===\n", t7.round(2).to_string(index=False))
adm = d[d.wave == 2025].groupby("cnt")[NAT].apply(lambda g: int((g.notna().sum() >= 100).sum()))
d[d.wave == 2025].groupby("cnt")[NAT].apply(lambda g: (g.notna().sum() >= 100).astype(int)).rename(
    columns=str.upper).to_csv(C.TABLES / "national_items_by_system.csv")
print(f"national items administered per system: mean {adm.mean():.2f}, min {adm.min()}, max {adm.max()}")

# C ---------------------------------------------------------------------------------------------
o22 = (d.wave == 2022).to_numpy()
SUB = {"Cultural: books, book types, instruments, art": ["st255q01ja"] + BT + ["st251q06ja", "st251q07ja"],
       "Living conditions: own room, internet, cars, bathrooms, toilets":
           ["st250q01ja", "st250q05ja", "st251q01ja", "st251q03ja", "st251q04ja"],
       "Technology: computer, software, phone, devices":
           ["st250q02ja", "st250q03ja", "st250q04ja"] + [c.lower() for c in C.DEV] + ["st253q01ja", "st254q06ja"]}
rows = []
for name, items in SUB.items():
    Z = np.column_stack([zscore(d[c], w, o22) for c in items])
    ok = (np.isfinite(Z).sum(axis=1) >= max(2, len(items) // 2)) & o22
    n = np.isfinite(Z).sum(axis=1)
    d["_sub"] = np.where(ok, np.nansum(Z, axis=1) / np.maximum(n, 1), np.nan)
    gaps = []
    for _, g in d[o22 & d["_sub"].notna()].groupby("cnt"):
        q = equal_weight_quartile(g["_sub"], g.w_fstuwt)
        gaps.append(wmean(g.score[q == 4], g.w_fstuwt[q == 4]) - wmean(g.score[q == 1], g.w_fstuwt[q == 1]))
    rows.append(dict(subscale=name, r_score=corr_oecd(2022, "_sub"), r_homepos_pub=corr_oecd(2022, "_sub", "homepos"),
                     r_homepos_har=corr_oecd(2022, "_sub", "homepos_h"), gap_q4_q1=np.mean(gaps)))
t8 = pd.DataFrame(rows)
t8.to_csv(C.TABLES / f"subscales_2022_{DOM}.csv", index=False)
print("\n=== subscales of the 2022 items ===\n", t8.round(3).to_string(index=False))

# D ---------------------------------------------------------------------------------------------
rows = []
for wave in (2022, 2025):
    m = (d.wave == wave).to_numpy()
    Z = np.column_stack([zscore(d[c], w, m) for c in COMMON])
    ok = m & np.isfinite(Z).all(axis=1) & d.homepos.notna().to_numpy()
    X = np.column_stack([np.ones(ok.sum()), Z[ok]])
    y, ww = d.homepos.to_numpy("float64")[ok], w[ok]
    b = np.linalg.lstsq(X * np.sqrt(ww)[:, None], y * np.sqrt(ww), rcond=None)[0]
    res = np.full(len(d), np.nan)
    res[ok] = y - X @ b
    d["_res"] = res
    r2 = 1 - np.average((y - X @ b) ** 2, weights=ww) / np.average((y - np.average(y, weights=ww)) ** 2, weights=ww)
    rows.append(dict(wave=wave, r2_common_items=r2, res_r_score=corr_oecd(wave, "_res"),
                     res_r_booktypes=corr_oecd(wave, "_res", "n_booktypes") if wave == 2022 else np.nan,
                     res_r_national_yes=corr_oecd(wave, "_res", "n_national_yes") if wave == 2025 else np.nan,
                     res_r_hisei=corr_oecd(wave, "_res", "hisei")))
tr = pd.DataFrame(rows)
tr.to_csv(C.TABLES / f"homepos_residual_{DOM}.csv", index=False)
print("\n=== Residual of the published HOMEPOS on the 16 common items ===\n", tr.round(3).to_string(index=False))
