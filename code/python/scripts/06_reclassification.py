"""Step 6. Who is classified differently by the published and the harmonized HOMEPOS (Tables 3 and 4),
and which cycle drives the difference between the two gap changes (levels of the Q4 - Q1 gap, taken from
the quartile table of step 5)."""
import numpy as np
import pandas as pd

from lib import config as C
from lib.io_utils import load_base, load_table
from lib.stats import equal_weight_quartile, wcorr, wmean

d = load_base(["wave", "cnt", "w_fstuwt", "math", "homepos", "hisei", "paredint", "books7",
                        "n_booktypes", "n_national_yes", "n_national_adm", "immig"])
d["homepos_h"] = load_table("indices_h", ["homepos_h"]).homepos_h.to_numpy()
d = d[d.homepos.notna() & d.homepos_h.notna()].copy()
d["q_pub"] = d["q_har"] = 0
for _, g in d.groupby(["cnt", "wave"]):
    w = g.w_fstuwt.to_numpy()
    d.loc[g.index, "q_pub"] = equal_weight_quartile(g.homepos, w)
    d.loc[g.index, "q_har"] = equal_weight_quartile(g.homepos_h, w)
d["moves"] = (d.q_pub != d.q_har).astype(float)


def by_country(g, f):
    return np.mean([f(x) for _, x in g.groupby("cnt")])


rows = []
for wave in (2022, 2025):
    g = d[d.wave == wave]
    rows.append({
        "wave": wave,
        "change_quartile_pct": by_country(g, lambda x: wmean(x.moves, x.w_fstuwt)) * 100,
        "pubQ4_still_Q4_pct": by_country(g, lambda x: wmean((x.q_har == 4)[x.q_pub == 4].astype(float),
                                                            x.w_fstuwt[x.q_pub == 4])) * 100,
        "pubQ1_still_Q1_pct": by_country(g, lambda x: wmean((x.q_har == 1)[x.q_pub == 1].astype(float),
                                                            x.w_fstuwt[x.q_pub == 1])) * 100,
        "r_within_country_unweighted": by_country(g, lambda x: np.corrcoef(x.homepos, x.homepos_h)[0, 1]),
        "r_within_country_weighted": by_country(g, lambda x: wcorr(x.homepos, x.homepos_h, x.w_fstuwt)),
    })
t3 = pd.DataFrame(rows).set_index("wave")
t3.to_csv(C.TABLES / "table3_reclassification.csv")
print("=== Table 3 ===\n", t3.round(3).T.to_string())

rows = []
for wave in (2022, 2025):
    g = d[d.wave == wave]
    groups = {"In Q4 under both": (g.q_pub == 4) & (g.q_har == 4),
              "Published Q4, not harmonized Q4": (g.q_pub == 4) & (g.q_har != 4),
              "Harmonized Q4, not published Q4": (g.q_pub != 4) & (g.q_har == 4),
              "In Q1 under both": (g.q_pub == 1) & (g.q_har == 1),
              "Published Q1, not harmonized Q1": (g.q_pub == 1) & (g.q_har != 1),
              "Harmonized Q1, not published Q1": (g.q_pub != 1) & (g.q_har == 1)}
    for name, m in groups.items():
        x = g[m]
        r = {"wave": wave, "group": name, "pct_students": x.w_fstuwt.sum() / g.w_fstuwt.sum() * 100}
        for v in ["math", "hisei", "paredint", "books7", "n_booktypes", "n_national_yes", "n_national_adm"]:
            r[v] = wmean(x[v], x.w_fstuwt)
        rows.append(r)
t4 = pd.DataFrame(rows)
t4.to_csv(C.TABLES / "table4_mover_profiles.csv", index=False)
print("\n=== Table 4 (pooled students, final weights) ===\n", t4.round(2).to_string(index=False))

for wave in (2022, 2025):
    g = d[d.wave == wave]
    ct = pd.crosstab(g.q_pub, g.q_har, values=g.w_fstuwt, aggfunc="sum", normalize=True) * 100
    ct.to_csv(C.TABLES / f"transition_matrix_{wave}.csv")


# Levels of the Q4 - Q1 gap (Section 3.4): from the headline quartile table of step 5, so that they
# refer to the same sample and plausible-value treatment as Table 2 and Table A.1.
o = pd.read_csv(C.TABLES / "quartiles_math.csv")
o = o[o.cnt == "OECD"].set_index("index")
out = pd.DataFrame({"gap_2022": [o.loc["homepos", "Q4-Q1_2022"], o.loc["homepos_h", "Q4-Q1_2022"]],
                    "gap_2025": [o.loc["homepos", "Q4-Q1_2025"], o.loc["homepos_h", "Q4-Q1_2025"]]},
                   index=["HOMEPOS published", "HOMEPOS harmonized"])
out["change"] = out.gap_2025 - out.gap_2022
out.to_csv(C.TABLES / "gap_levels_homepos.csv")
print("\n=== Levels of the Q4 - Q1 gap, mathematics, 36 systems ===\n", out.round(1).to_string())
