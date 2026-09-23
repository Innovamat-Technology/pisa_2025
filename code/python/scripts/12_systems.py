"""Step 12. Results across education systems.

A. Q1 and Q4 changes by system under the published and harmonized ESCS and HOMEPOS
B. across systems: correlation of the change in the Q4 - Q1 gap (published, harmonized, and their
   difference) with log GDP per capita, the mean score in 2022 and the mean ESCS in 2022
Usage: python code/python/scripts/12_systems.py [math|read|scie]
"""
import sys

import numpy as np
import pandas as pd

from lib import config as C
from lib.io_utils import load_base
from lib.stats import wmean

DOM = sys.argv[1] if len(sys.argv) > 1 else "math"
q = pd.read_csv(C.TABLES / f"quartiles_{DOM}.csv")
c = q[q.cnt != "OECD"]
wide = c.pivot(index="cnt", columns="index")
out = pd.DataFrame({f"{idx}_{col}": wide[(col, idx)] for idx in ("escs", "escs_h", "homepos", "homepos_h")
                    for col in ("Q1_change", "Q4_change", "Q4-Q1_change", "Q4-Q1_se")})
out = out.sort_values("escs_Q4-Q1_change")
out.to_csv(C.TABLES / f"systems_q1_q4_{DOM}.csv")
for idx in ("escs", "escs_h", "escs_pca"):
    ch, se = wide[("Q4-Q1_change", idx)], wide[("Q4-Q1_se", idx)]
    print(f"{DOM} {idx}: gap change negative in {(ch < 0).sum()} of {len(ch)} systems, "
          f"significant narrowing in {(ch / se < -1.96).sum()}, significant widening in {(ch / se > 1.96).sum()}")

PVc = [f"pv{i}{DOM}" for i in range(1, 11)]
b = load_base(["wave", "cnt", "w_fstuwt", "escs"] + PVc)
b = b[b.wave == 2022]
b["score"] = b[PVc].mean(axis=1)
s = pd.DataFrame({"mean_score_2022": b.groupby("cnt").apply(lambda g: wmean(g.score, g.w_fstuwt), include_groups=False),
                  "mean_escs_2022": b.groupby("cnt").apply(lambda g: wmean(g.escs, g.w_fstuwt), include_groups=False)})
gdp = pd.read_csv(C.ROOT / "reference" / "gdp_per_capita_ppp_2022.csv").set_index("cnt")
s["log_gdp_pc"] = np.log(gdp.gdp_pc_ppp_2022)
s["published"], s["harmonized"] = wide[("Q4-Q1_change", "escs")], wide[("Q4-Q1_change", "escs_h")]
s["mismatch"] = s.published - s.harmonized
s.to_csv(C.TABLES / f"systems_income_{DOM}.csv")
r = s.corr().loc[["mismatch", "published", "harmonized"], ["log_gdp_pc", "mean_score_2022", "mean_escs_2022"]]
r.to_csv(C.TABLES / f"systems_correlations_{DOM}.csv")
print(f"\n=== {DOM}: correlations across {len(s)} systems ===\n", r.round(2).to_string())
print("\nlargest mismatches:\n", s.mismatch.sort_values().round(1).head(6).to_string(),
      "\nsmallest:\n", s.mismatch.abs().sort_values().round(1).head(4).to_string())
