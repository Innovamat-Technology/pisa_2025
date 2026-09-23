"""Small weighted-statistics helpers."""
import numpy as np

from lib import config as C


def wmean(x, w):
    x, w = np.asarray(x, "float64"), np.asarray(w, "float64")
    m = np.isfinite(x)
    return np.average(x[m], weights=w[m]) if m.any() else np.nan


def wcorr(x, y, w, min_n=100):
    x, y, w = (np.asarray(a, "float64") for a in (x, y, w))
    m = np.isfinite(x) & np.isfinite(y)
    if m.sum() < min_n:
        return np.nan
    x, y, w = x[m], y[m], w[m]
    mx, my = np.average(x, weights=w), np.average(y, weights=w)
    vx, vy = np.average((x - mx) ** 2, weights=w), np.average((y - my) ** 2, weights=w)
    if vx == 0 or vy == 0:
        return np.nan
    return np.average((x - mx) * (y - my), weights=w) / np.sqrt(vx * vy)


def equal_weight_quartile(x, w, seed=C.SEED):
    """Quartile 1..4, each holding 25% of the weight; ties are broken at random."""
    x, w = np.asarray(x, "float64"), np.asarray(w, "float64")
    rng = np.random.default_rng(seed)
    o = np.lexsort((rng.random(len(x)), x))
    f = (np.cumsum(w[o]) - w[o]) / w.sum()
    q = np.empty(len(x), int)
    q[o] = np.digitize(f, [.25, .5, .75])
    return q + 1


def cell_weights(d):
    """Weights under which every country-by-cycle cell counts the same (senate-style)."""
    w = d.w_fstuwt.to_numpy("float64").copy()
    g = d.groupby(["cnt", "wave"]).ngroup().to_numpy()
    return w / np.bincount(g, w)[g]


def zscore(x, w, mask=None):
    """Weighted z-score; mean and SD are taken over `mask` (default: all valid rows)."""
    x = np.asarray(x, "float64")
    ok = np.isfinite(x) if mask is None else np.isfinite(x) & mask
    mu = np.average(x[ok], weights=w[ok])
    sd = np.sqrt(np.average((x[ok] - mu) ** 2, weights=w[ok]))
    return (x - mu) / sd
