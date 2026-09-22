"""Step 4. Harmonised components and composites, standardised over the pooled 2022 + 2025 sample.

HISEI  : same ISEI scale in both cycles, only standardised.
PARED  : 3 years -> 6 and 14.5 -> 14 (values that do not exist in 2025), then standardised.
HOMEPOS: EAP score of the common-item graded response model (step 3).
Books  : ST255, seven identical categories in both cycles.
Composite (escs_h): the OECD rule (escs_rule.py) applied to the three harmonised components in
their original metric, with the two cycles pooled: regression imputation of a single missing
component within system and cycle, senate-weight standardisation, equal-weight mean,
re-standardisation. escs_pca, the first principal component, is kept as a robustness check
(step 10 has eight more).
"""
import numpy as np

from lib import config as C
from lib.io_utils import load_base, load_table, save_table
from lib.escs_rule import escs
from lib.stats import cell_weights, zscore

d = load_base(["wave", "cnt", "cntstuid", "w_fstuwt", "escs", "hisei", "paredint", "books7"])
g = load_table("homepos_grm").iloc[:len(d)]
assert (g.cntstuid.to_numpy() == d.cntstuid.to_numpy()).all()
w = cell_weights(d)

for wave in (2022, 2025):
    print(f"PARED values {wave}:", sorted(d[d.wave == wave].paredint.dropna().unique()))
d["hisei_h"] = zscore(d.hisei, w)
d["pared_h"] = zscore(d.paredint.replace({3.0: 6.0, 14.5: 14.0}), w)
d["homepos_h"] = zscore(g.homepos_grm, w)
d["books_h"] = zscore(d.books7, w)

group = d.groupby(["cnt", "wave"], sort=False).ngroup().to_numpy()
pared_c = d.paredint.replace({3.0: 6.0, 14.5: 14.0}).to_numpy("float64")
RAW = np.column_stack([d.hisei.to_numpy("float64"), pared_c, g.homepos_grm.to_numpy("float64")])
d["escs_h"], _, pct_imputed = escs(RAW, group, w)
print(f"escs_h (OECD rule): one component imputed for {pct_imputed:.1f}% of students; "
      f"valid for {np.isfinite(d.escs_h).mean():.1%}")

COMP = ["hisei_h", "pared_h", "homepos_h"]
X = d[COMP].to_numpy("float64")
n_valid = np.isfinite(X).sum(axis=1)
Xi = np.nan_to_num(X)
full = n_valid == 3
val, vec = np.linalg.eigh(np.cov(Xi[full].T, aweights=w[full]))
v = vec[:, -1] if vec[0, -1] > 0 else -vec[:, -1]
d["escs_pca"] = zscore(np.where(n_valid >= 2, Xi @ v, np.nan), w)
print("escs_pca loadings:", dict(zip(COMP, v.round(3))), f"variance explained {val[-1] / val.sum():.3f}")
print(f"r with the published ESCS: OECD rule {d[['escs_h', 'escs']].corr().iloc[0, 1]:.3f}, "
      f"principal component {d[['escs_pca', 'escs']].corr().iloc[0, 1]:.3f}; "
      f"r(escs_h, escs_pca) = {d[['escs_h', 'escs_pca']].corr().iloc[0, 1]:.4f}")
for c in COMP + ["escs_h", "escs_pca"]:
    m = [np.average(x[c].dropna(), weights=x.w_fstuwt[x[c].notna()]) for _, x in d.groupby(["wave", "cnt"])]
    n = len(m) // 2
    print(f"  {c:10s} OECD mean 2022 {np.mean(m[:n]):+.3f}  2025 {np.mean(m[n:]):+.3f}")
save_table(d[["wave", "cnt", "cntstuid"] + COMP + ["books_h", "escs_h", "escs_pca"]], "indices_h")
