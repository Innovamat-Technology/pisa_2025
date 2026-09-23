"""The OECD rule for the ESCS composite, applied over a pooled sample of cycles.

PISA 2025 Technical Report, chapter 22, "Computation of ESCS" (identical to PISA 2022):
  1. For students missing exactly one of the three components, the missing component is
     predicted from the other two with a regression fitted within each country/economy on
     students with complete data, plus a random draw from a normal with the standard deviation
     of that regression's residuals. Students missing two or more components get no ESCS.
  2. Each component (imputations included) is standardized to mean 0 and SD 1 with every
     country weighing the same (senate weights).
  3. The three standardized components are averaged with equal weights.
  4. The average is standardized again.
The only departure from the OECD is the scope of the standardization: here the pool is all the
cycles analyzed together, so that the metric is not re-anchored in each cycle.
"""
import numpy as np

SEED = 20252022


def zpool(x, w):
    """Weighted z-score over every valid observation."""
    x = np.asarray(x, "float64")
    m = np.isfinite(x) & np.isfinite(w)
    mu = np.average(x[m], weights=w[m])
    sd = np.sqrt(np.average((x[m] - mu) ** 2, weights=w[m]))
    return (x - mu) / sd


def impute(X, group, seed=SEED, noise=True, min_complete=30):
    """Regression imputation of a single missing component within each group.

    X: (n, 3) raw components with NaN where missing. Returns the completed array (rows with two
    or more missing set to NaN throughout), a mask of imputed cells and the count of missing
    components per student before imputation.
    """
    X = np.array(X, dtype="float64", copy=True)
    missing = ~np.isfinite(X)
    n_missing = missing.sum(axis=1)
    imputed = np.zeros_like(missing)
    rng = np.random.default_rng(seed)
    group = np.asarray(group)
    for g in np.unique(group):
        sel = np.where(group == g)[0]
        Xg, mg = X[sel], missing[sel]
        complete = mg.sum(axis=1) == 0
        if complete.sum() < min_complete:
            continue
        for j in range(3):
            target = (mg.sum(axis=1) == 1) & mg[:, j]
            if not target.any():
                continue
            others = [k for k in range(3) if k != j]
            A = np.column_stack([np.ones(complete.sum()), Xg[complete][:, others]])
            y = Xg[complete, j]
            b = np.linalg.lstsq(A, y, rcond=None)[0]
            sd = (y - A @ b).std(ddof=A.shape[1])
            pred = np.column_stack([np.ones(target.sum()), Xg[target][:, others]]) @ b
            if noise:
                pred = pred + rng.normal(0.0, sd, target.sum())
            X[sel[target], j] = pred
            imputed[sel[target], j] = True
    X[n_missing >= 2] = np.nan
    return X, imputed, n_missing


def escs(X, group, w, imputation="regression", noise=True, seed=SEED):
    """ESCS by the OECD rule. Returns (score, standardized components, share of students imputed).

    imputation: "regression" (the OECD rule), "mean" (mean of the available standardized
    components, no imputation) or "complete" (students with the three components only).
    """
    X = np.asarray(X, "float64")
    n_missing = (~np.isfinite(X)).sum(axis=1)
    if imputation == "regression":
        Xi, imp, n_missing = impute(X, group, seed, noise)
        Z = np.column_stack([zpool(Xi[:, j], w) for j in range(3)])
        prelim = Z.mean(axis=1)
    elif imputation == "mean":
        Z = np.column_stack([zpool(X[:, j], w) for j in range(3)])
        with np.errstate(invalid="ignore"):
            prelim = np.where(n_missing <= 1, np.nanmean(Z, axis=1), np.nan)
        imp = np.zeros_like(X, bool)
    elif imputation == "complete":
        Z = np.column_stack([zpool(X[:, j], w) for j in range(3)])
        prelim = np.where(n_missing == 0, Z.mean(axis=1), np.nan)
        imp = np.zeros_like(X, bool)
    else:
        raise ValueError(imputation)
    prelim = np.where(np.isfinite(prelim), prelim, np.nan)
    return zpool(prelim, w), Z, float(imp.any(axis=1).mean() * 100)
