"""Step 7. Level of the Q4 - Q1 gap by index and cycle, 2015-2025, published and harmonised indices.

The harmonised four-cycle indices use the thirteen possessions items whose concept exists in every
cycle, recoded to common response categories, with one graded response model for the pooled cycles;
HISEI standardised over the pool; parental education on the common years-of-schooling scale
{6, 9, 12, 14, 16} (2015 rebuilt from HISCED with the mapping observed in the 2018 file).
Systems: OECD members (as flagged in each file) present in every cycle that is available locally.
Gaps: equal-weight quartiles recomputed under each replicate weight, ten plausible values.

The counts of televisions, tablets and e-book readers were asked as None / One / Two / Three or
more up to 2018 and as None / 1-2 / 3-5 / More than 5 from 2022; both are collapsed to none / 1-2 /
3 or more. Computers were one count up to 2018 and two (desktops, laptops) from 2022, so the item
is reduced to "at least one computer". Works of art were yes/no up to 2018 and a count afterwards.

The four-cycle composite (escs_h4) follows the OECD rule of escs_rule.py with the four cycles
pooled: regression imputation of a single missing component within system and cycle, senate-weight
standardisation, equal-weight mean, re-standardisation. Two variants are kept: the mean of the
available components without imputation, and the first principal component.
"""
import numpy as np
import pandas as pd

from lib import brr
from lib import config as C
from lib import grm
from lib.io_utils import load_table, save_table, table_exists
from lib.escs_rule import escs
from lib.stats import cell_weights, zscore

YEARS = [y for y in (2015, 2018, 2022, 2025) if table_exists(f"stu_{y}")]
if len(YEARS) < 4:
    raise SystemExit(f"cycles available: {YEARS}; the series needs 2015, 2018, 2022 and 2025 in data/extract/")

# item -> (variable in 2015/2018, variable(s) in 2022/2025, kind)
ITEMS13 = {"room": ("st011q02ta", "st250q01ja", "bin"), "computer": ("st011q04ta", "st250q02ja", "bin"),
           "software": ("st011q05ta", "st250q03ja", "bin"), "internet": ("st011q06ta", "st250q05ja", "bin"),
           "art": ("st011q09ta", "st251q07ja", "bin_from_count"),
           "instruments": ("st012q09na", "st251q06ja", "count4"), "cars": ("st012q02ta", "st251q01ja", "count4"),
           "bathrooms": ("st012q03ta", "st251q03ja", "count4"),
           "televisions": ("st012q01ta", "st254q01ja", "band3"), "tablets": ("st012q07na", "st254q04ja", "band3"),
           "ereaders": ("st012q08na", "st254q05ja", "band3"),
           "computers": ("st012q06na", ("st254q02ja", "st254q03ja"), "any_computer"),
           "books": ("books6", "st255q01ja", "books6")}


def old_band(x):      # None / One / Two / Three or more  ->  none / 1-2 / 3+
    return x.where(x.between(1, 4)).map({1: 0.0, 2: 1.0, 3: 1.0, 4: 2.0})


def new_band(x):      # None / 1-2 / 3-5 / More than 5 / I don't know  ->  none / 1-2 / 3+
    return x.where(x.between(1, 4)).map({1: 0.0, 2: 1.0, 3: 2.0, 4: 2.0})


def recode(g, year):
    out = pd.DataFrame(index=g.index)
    for name, (old, new, kind) in ITEMS13.items():
        if year <= 2018:
            x = g[old]
            if kind in ("bin", "bin_from_count"):
                out[name] = x.where(x.isin([1, 2])).map({1: 1.0, 2: 0.0})
            elif kind == "count4":
                out[name] = x.where(x.between(1, 4)) - 1
            elif kind == "band3":
                out[name] = old_band(x)
            elif kind == "any_computer":
                out[name] = (x.where(x.between(1, 4)) >= 2).astype(float).where(x.notna())
            else:
                out[name] = x.where(x.between(1, 6)) - 1
        else:
            if kind == "bin":
                out[name] = g[new].where(g[new].isin([1, 2])).map({1: 1.0, 2: 0.0})
            elif kind == "bin_from_count":
                out[name] = (g[new].where(g[new].between(1, 4)) > 1).astype(float).where(g[new].between(1, 4))
            elif kind == "count4":
                out[name] = g[new].where(g[new].between(1, 4)) - 1
            elif kind == "band3":
                out[name] = new_band(g[new])
            elif kind == "any_computer":        # desktops and laptops asked separately
                a, b = (g[v].where(g[v].between(1, 4)) for v in new)
                out[name] = ((a >= 2) | (b >= 2)).astype(float).where(g[new[0]].notna() | g[new[1]].notna())
            else:                               # seven book categories: "none" and "1-10" merged
                out[name] = (g[new].where(g[new].between(1, 7)) - 1).clip(lower=1) - 1
    return out


PV = [f"pv{i}{dom}" for dom in C.DOMAINS for i in range(1, 11)]
parts, W = [], []
for y in YEARS:
    g = load_table(f"stu_{y}")
    it = recode(g, y)
    keep = ["wave", "cnt", "cntstuid", "w_fstuwt", "escs", "homepos", "hisei", "paredint"] + PV
    if y <= 2018:
        keep.append("hisced")
    parts.append(pd.concat([g[keep], it], axis=1))
    W.append(np.load(C.EXTRACT / f"wts_{y}.npy"))
d = pd.concat(parts, ignore_index=True)
W = np.vstack(W)
common = set.intersection(*[set(d[d.wave == y].cnt) for y in YEARS]) - set(C.EXCLUDE)
keep = d.cnt.isin(common).to_numpy()
d, W = d[keep].reset_index(drop=True), np.column_stack([d.w_fstuwt.to_numpy("float64")[keep], W[keep]])
print(f"{len(common)} OECD systems present in {YEARS}; N = {len(d):,}")

# parental education on the common scale
if 2015 in YEARS:
    m18 = d[(d.wave == 2018) & d.hisced.notna() & d.paredint.notna()]
    mapping = m18.groupby("hisced").paredint.agg(lambda s: s.mode().iloc[0]).to_dict()
    print("HISCED -> years of schooling observed in 2018:", mapping)
    is15 = d.wave == 2015
    d.loc[is15, "paredint"] = d.loc[is15, "hisced"].map(mapping)
d["pared_c"] = d.paredint.replace({3.0: 6.0, 14.5: 14.0})
for y in YEARS:
    print(f"  PARED values {y}:", sorted(d[d.wave == y].pared_c.dropna().unique()))

# possessions: one graded response model for all cycles
names = list(ITEMS13)
X = np.full((len(d), len(names)), -1, dtype=np.int8)
for j, c in enumerate(names):
    v = d[c].to_numpy("float64")
    X[np.isfinite(v), j] = v[np.isfinite(v)].astype(np.int8)
w = cell_weights(d)
eap, A, B = grm.fit_and_score(X, w / w.sum() * len(d), min_items=8)
pd.DataFrame({"item": names, "a": np.round(A, 3), "thresholds": [np.round(b, 3).tolist() for b in B]}).to_csv(
    C.TABLES / "grm_parameters_four_cycles.csv", index=False)
d["homepos_h4"] = zscore(eap, w)
for y in YEARS:
    g = d[d.wave == y]
    print(f"  {y}: r(four-cycle HOMEPOS, published HOMEPOS) = {g[['homepos', 'homepos_h4']].corr().iloc[0, 1]:.3f}")

d["hisei_h4"], d["pared_h4"] = zscore(d.hisei, w), zscore(d.pared_c, w)
RAW = np.column_stack([d.hisei.to_numpy("float64"), d.pared_c.to_numpy("float64"), eap])
group = d.groupby(["cnt", "wave"], sort=False).ngroup().to_numpy()
d["escs_h4"], _, pct_imputed = escs(RAW, group, w)
d["escs_mean4"], _, _ = escs(RAW, group, w, imputation="mean")
print(f"four-cycle composite, OECD rule: one component imputed for {pct_imputed:.1f}% of students")
comp = d[["hisei_h4", "pared_h4", "homepos_h4"]].to_numpy("float64")
n_valid, Xi = np.isfinite(comp).sum(axis=1), np.nan_to_num(comp)
full = n_valid == 3
_, vec = np.linalg.eigh(np.cov(Xi[full].T, aweights=w[full]))
v = vec[:, -1] if vec[0, -1] > 0 else -vec[:, -1]
print("loadings of the principal-component variant:", v.round(3))
d["escs_pca4"] = np.where(n_valid >= 2, Xi @ v, np.nan)
save_table(d[["wave", "cnt", "cntstuid", "homepos_h4", "hisei_h4", "pared_h4", "escs_h4", "escs_mean4", "escs_pca4"]], "indices_four_cycles")

INDICES = {"escs": "ESCS, published", "escs_h4": "ESCS, harmonised (four cycles)",
           "escs_mean4": "ESCS, harmonised (four cycles), no imputation",
           "escs_pca4": "ESCS, harmonised (four cycles), principal component", "homepos": "HOMEPOS, published",
           "homepos_h4": "HOMEPOS, harmonised (four cycles)", "hisei": "HISEI", "pared_c": "PARED (common scale)",
           "books": "Books at home (six categories)"}
for dom in C.DOMAINS:
    PVc = [f"pv{i}{dom}" for i in range(1, 11)]
    TH = {}
    for (cnt, wave), g in d.groupby(["cnt", "wave"], sort=True):
        pos = g.index.to_numpy()
        P = g[PVc].to_numpy("float64")
        ok = np.isfinite(P).all(axis=1)
        for idx in INDICES:
            m = ok & g[idx].notna().to_numpy()
            if m.sum() >= 200:
                TH[(idx, wave, cnt)] = brr.theta_quartiles(g[idx].to_numpy("float64")[m], W[pos][m], P[m])
    rows = []
    for idx, label in INDICES.items():
        cnts = sorted(set.intersection(*[{k[2] for k in TH if k[0] == idx and k[1] == y} for y in YEARS]))
        r = {"index": idx, "label": label, "n_systems": len(cnts)}
        for y in YEARS:
            gap, se = brr.contrast(np.mean([TH[(idx, y, c)] for c in cnts], axis=0), [-1, 0, 0, 1])
            r[f"y{y}"], r[f"se{y}"] = gap, se
        rows.append(r)
    t = pd.DataFrame(rows)
    t.to_csv(C.TABLES / f"gap_series_{dom}.csv", index=False)
    print(f"\n=== {dom}: level of the Q4 - Q1 gap ===\n", t[["label", "n_systems"] + [f"y{y}" for y in YEARS]].round(1).to_string(index=False))
