"""Step 2. Working file: OECD systems present in 2022 and 2025, items recoded to one fixed metric."""
import numpy as np
import pandas as pd

from lib import config as C
from lib.io_utils import load_table, save_table

d = pd.concat([load_table("stu_2022"), load_table("stu_2025")], ignore_index=True)
W = np.vstack([np.load(C.EXTRACT / "wts_2022.npy"), np.load(C.EXTRACT / "wts_2025.npy")])
both = sorted(set(d[d.wave == 2022].cnt) & set(d[d.wave == 2025].cnt))
print("OECD systems in only one cycle:", sorted(set(d.cnt) - set(both)))

# Costa Rica has no ESCS, HISEI or PARED in either file
for wave in (2022, 2025):
    g = d[(d.cnt == "CRI") & (d.wave == wave)]
    print(f"  CRI {wave}: n={len(g)}, valid ESCS {g.escs.notna().mean():.1%}, "
          f"HISEI {g.hisei.notna().mean():.1%}, PARED {g.paredint.notna().mean():.1%}, "
          f"HOMEPOS {g.homepos.notna().mean():.1%}")

keep = d.cnt.isin(both).to_numpy()
d, W = d[keep].reset_index(drop=True), W[keep]
# analysis sample first; excluded systems stay at the end of the file because they still enter the
# calibration of the possessions model (step 3) and the books rule of step 11
d["in_sample"] = (~d.cnt.isin(C.EXCLUDE)).astype(int)
order = np.argsort(-d.in_sample.to_numpy(), kind="stable")
d, W = d.iloc[order].reset_index(drop=True), W[order]
print(f"{d[d.in_sample == 1].cnt.nunique()} systems in the analysis sample, N = {int(d.in_sample.sum()):,} "
      f"(+ {int((d.in_sample == 0).sum()):,} students of {C.EXCLUDE})")

low = [c.lower() for c in C.COMMON + C.BOOKTYPES + C.DROPPED_OTHER + C.NATIONAL]
print("\nraw value counts of the items that are recoded below")
for c in ["st254q01ja", "st256q01ja", "st253q01ja", "st254q06ja", "st251q02ja"]:
    print(f"  {c}: {d[c].value_counts().sort_index().astype(int).to_dict()}")

for c in [x.lower() for x in C.BIN + C.NATIONAL]:            # 1 = yes, 2 = no  ->  1 / 0
    d[c] = d[c].where(d[c].isin([1, 2])).map({1: 1.0, 2: 0.0})
# ST253 (number of screen devices) has eight ordered categories
d["st253q01ja"] = d["st253q01ja"].where(d["st253q01ja"].between(1, 8))
for c in [x.lower() for x in C.CNT4 + C.DEV + C.BOOKTYPES + ["ST254Q06JA", "ST251Q02JA"]]:
    d[c] = d[c].where(d[c].between(1, 4))                    # 1 = none ... 4; 5 = "I don't know"
b = C.BOOKS.lower()
d[b] = d[b].where(d[b].between(1, 7))
d["books7"] = d[b]
common = d[[c.lower() for c in C.COMMON]]
d["n_common"] = common.notna().sum(axis=1)
# simple fixed-item possessions score: mean of the 16 items, each standardised over the pooled file
d["cpos"] = ((common - common.mean()) / common.std()).mean(axis=1).where(d.n_common >= 10)
bt = d[[c.lower() for c in C.BOOKTYPES]]
d["n_booktypes"] = (bt >= 2).sum(axis=1).where(bt.notna().sum(axis=1) >= 6)
nat = d[[c.lower() for c in C.NATIONAL]]
d["n_national_yes"] = nat.sum(axis=1, min_count=1)
d["n_national_adm"] = nat.notna().sum(axis=1)
d["math"] = d[[f"pv{i}math" for i in range(1, 11)]].mean(axis=1)

save_table(d, "base")
np.save(C.INTERIM / "base_weights.npy", np.column_stack([d.w_fstuwt.to_numpy("float64"), W]))
cov = d.groupby("wave")[["escs", "hisei", "paredint", "homepos", "books7"]].apply(
    lambda g: (g.notna().mean() * 100).round(1))
print("\nunweighted coverage (%)\n", cov.to_string())
