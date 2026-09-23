"""Step 3. Harmonized HOMEPOS: the OECD item response model on the 16 common items.

Two-parameter logistic model for the dichotomous items and generalized partial credit model for the
polytomous ones (lib/irt.py), one set of item parameters for the pooled 2022 + 2025 OECD sample
(concurrent calibration), every country-by-cycle cell weighted equally, marginal maximum likelihood
by EM on a fixed grid, weighted likelihood estimates (WLE) as scores. Students need at least 10 valid
items to be scored.
"""
import numpy as np
import pandas as pd

from lib import config as C
from lib import irt
from lib.io_utils import load_table, save_table
from lib.stats import cell_weights

ITEMS = [c.lower() for c in C.COMMON]
d = load_table("base", ["wave", "cnt", "cntstuid", "w_fstuwt", "homepos"] + ITEMS)   # every row, see step 2

X = np.full((len(d), len(ITEMS)), -1, dtype=np.int8)          # -1 = no answer
for j, c in enumerate(ITEMS):
    v = d[c].to_numpy("float64")
    k = v if c in [b.lower() for b in C.BIN] else v - 1       # categories start at 0
    m = np.isfinite(k)
    X[m, j] = k[m].astype(np.int8)
K = [int(X[X[:, j] >= 0, j].max()) + 1 for j in range(len(ITEMS))]
print("items and categories:", dict(zip(ITEMS, K)))

w = cell_weights(d)
A, B = irt.fit(X, w / w.sum() * len(d))
d["homepos_irt"] = irt.wle(X, A, B, min_items=10)

par = pd.DataFrame({"item": [c.upper() for c in ITEMS], "label": [C.LABELS[c.upper()] for c in ITEMS],
                    "a": A.round(3), "steps": [np.round(b, 3).tolist() for b in B]})
par.to_csv(C.TABLES / "irt_parameters.csv", index=False)
print(par[["label", "a"]].sort_values("a", ascending=False).to_string(index=False))
for wave in (2022, 2025):
    g = d[d.wave == wave]
    print(f"  {wave}: r with published HOMEPOS {g[['homepos', 'homepos_irt']].corr().iloc[0, 1]:.3f}, "
          f"scored {g.homepos_irt.notna().mean():.1%}")
save_table(d[["wave", "cnt", "cntstuid", "homepos_irt"]], "homepos_irt")
