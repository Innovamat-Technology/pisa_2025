"""Step 3. Harmonised HOMEPOS: a graded response model on the 16 common items.

One set of item parameters for the pooled 2022 + 2025 OECD sample (concurrent calibration),
every country-by-cycle cell weighted equally, marginal maximum likelihood by EM on a fixed
grid, EAP scores. Students need at least 10 valid items to be scored.
"""
import numpy as np
import pandas as pd
from scipy.optimize import minimize

from lib import config as C
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
K = np.array([int(X[X[:, j] >= 0, j].max()) + 1 for j in range(len(ITEMS))])
print("items and categories:", dict(zip(ITEMS, K)))

w = cell_weights(d)
w = w / w.sum() * len(d)

Q = 25
th = np.linspace(-4, 4, Q)
prior = np.exp(-th ** 2 / 2)
prior /= prior.sum()


def probs(a, b, th):
    """(K, Q) probability of each category at each node."""
    z = a * (th[None, :] - b[:, None])
    P = 1 / (1 + np.exp(-z))                                   # P(X >= k), k = 1..K-1
    P = np.vstack([np.ones((1, len(th))), P, np.zeros((1, len(th)))])
    return np.clip(P[:-1] - P[1:], 1e-9, 1.0)


A = np.ones(len(ITEMS))
B = []
for j in range(len(ITEMS)):
    v = X[X[:, j] >= 0, j]
    cum = np.cumsum(np.bincount(v, minlength=K[j])[::-1])[::-1][1:] / len(v)
    B.append(np.clip(-np.log(cum / (1 - cum)), -3.5, 3.5))

obs = X >= 0


def posterior():
    L = np.tile(prior, (len(d), 1))
    for j in range(len(ITEMS)):
        P = probs(A[j], B[j], th)
        m = obs[:, j]
        L[m] *= P[X[m, j]]
        L[m] /= L[m].sum(axis=1, keepdims=True)
    return L


for it in range(40):
    post = posterior()                                         # E step
    change = 0.0
    for j in range(len(ITEMS)):                                # M step, item by item
        m = obs[:, j]
        R = np.zeros((K[j], Q))
        for k in range(K[j]):
            s = m & (X[:, j] == k)
            R[k] = (post[s] * w[s, None]).sum(axis=0)

        def nll(p):
            return -(R * np.log(probs(np.exp(p[0]), np.sort(p[1:]), th))).sum()

        r = minimize(nll, np.concatenate([[np.log(A[j])], B[j]]), method="Powell",
                     options=dict(maxiter=4000, xtol=1e-3, ftol=1e-4))
        a1, b1 = np.exp(r.x[0]), np.sort(r.x[1:])
        change = max(change, abs(a1 - A[j]), np.abs(b1 - B[j]).max())
        A[j], B[j] = a1, b1
    print(f"  iteration {it:2d}: largest parameter change {change:.4f}", flush=True)
    if change < 1e-3:
        break

eap = posterior() @ th
eap = np.where(obs.sum(axis=1) >= 10, eap, np.nan)
d["homepos_grm"] = eap

par = pd.DataFrame({"item": [c.upper() for c in ITEMS], "label": [C.LABELS[c.upper()] for c in ITEMS],
                    "a": A.round(3), "thresholds": [np.round(b, 3).tolist() for b in B]})
par.to_csv(C.TABLES / "grm_parameters.csv", index=False)
print(par[["label", "a"]].sort_values("a", ascending=False).to_string(index=False))
for wave in (2022, 2025):
    g = d[d.wave == wave]
    print(f"  {wave}: r with published HOMEPOS {g[['homepos', 'homepos_grm']].corr().iloc[0, 1]:.3f}, "
          f"scored {g.homepos_grm.notna().mean():.1%}")
save_table(d[["wave", "cnt", "cntstuid", "homepos_grm"]], "homepos_grm")
