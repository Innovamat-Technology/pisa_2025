"""BRR engine: quartiles recomputed under every replicate weight, ten plausible values, Fay 0.5.

theta arrays have shape (groups, 1 + 80 weights, 10 plausible values); column 0 of the
weight axis is the final student weight.
"""
import numpy as np

from lib import config as C

FAY = 1.0 / (C.N_REP * 0.25)          # 1 / (G * (1 - k)^2) with k = 0.5


def _quartile_per_replicate(x, W, rng, k=4):
    """(n, 81) codes 0..k-1: equal-weight groups (quartiles by default) recomputed with each weight column."""
    n, R = W.shape
    order = np.lexsort((rng.random(n), x))
    cum = np.cumsum(W[order], axis=0)
    frac = cum / cum[-1]
    code = np.zeros(frac.shape, np.int8)
    for cut in np.arange(1, k) / k:
        code += frac > cut
    # the student who crosses a cut belongs to the quartile below it
    code = np.vstack([np.zeros((1, R), np.int8), code[:-1]])
    out = np.empty_like(code)
    out[order] = code
    return out


def _aggregate(code, W, PV, k):
    """theta[g, r, m] = weighted mean of PV m in group g under weight r."""
    R, M = W.shape[1], PV.shape[1]
    th = np.full((k, R, M), np.nan)
    for r in range(R):
        c = code[:, r] if code.ndim == 2 else code
        w = W[:, r]
        den = np.bincount(c, w, minlength=k)
        for m in range(M):
            num = np.bincount(c, w * PV[:, m], minlength=k)
            with np.errstate(invalid="ignore", divide="ignore"):
                th[:, r, m] = num / den
    return th


def theta_quartiles(x, W, PV, seed=C.SEED, k=4):
    rng = np.random.default_rng(seed)
    return _aggregate(_quartile_per_replicate(x, W, rng, k), W, PV, k)


def quartile_codes(x, W, seed=C.SEED):
    """Quartile codes 0..3 under the final weight (same tie-breaking as theta_quartiles)."""
    rng = np.random.default_rng(seed)
    return _quartile_per_replicate(x, W, rng)[:, 0]


def theta_groups(code, W, PV, k):
    """Fixed groups (they do not depend on the replicate)."""
    return _aggregate(np.ascontiguousarray(code), W, PV, k)


def summarise(th):
    """theta (k, R, M) -> estimate, standard error (sampling + imputation variance)."""
    t0, tr = th[:, 0, :], th[:, 1:, :]
    v_samp = (FAY * ((tr - t0[:, None, :]) ** 2).sum(axis=1)).mean(axis=1)
    M = t0.shape[1]
    v_imp = (1 + 1 / M) * t0.var(axis=1, ddof=1) if M > 1 else 0.0
    return t0.mean(axis=1), np.sqrt(v_samp + v_imp)


def contrast(th, c):
    """Linear combination c (k,) of the groups -> (estimate, se)."""
    e, s = summarise(np.einsum("k,krm->rm", np.asarray(c, float), th)[None])
    return e[0], s[0]


def mean_change_se(se22, se25, domain):
    """SE of a 2022–2025 mean change: sampling, plausible values and OECD link error.

    The cycle SEs already contain sampling and plausible-value imputation variance.
    Add the common link variance once, including for an international mean: it does
    not shrink with the number of countries. For changes in within-cycle contrasts
    such as Q4-Q1, the additive link cancels; combine the contrast SEs without it.
    """
    return np.hypot(np.hypot(se22, se25), C.LINK_ERROR_2022_2025[domain])
