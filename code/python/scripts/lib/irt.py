"""Item response model for the possessions scale, the one the OECD uses for the PISA questionnaire
indices (PISA 2025 Technical Report, chapter 22): the two-parameter logistic model for dichotomous
items and the generalized partial credit model (GPCM, Muraki 1992) for polytomous ones, the 2PL
being the GPCM with two categories. Item parameters by marginal maximum likelihood (EM on a fixed
quadrature grid); person scores as weighted likelihood estimates (WLE, Warm 1989).

Parameterization: for an item with categories 0..m, discrimination a and step locations b_1..b_m,
P(X = k | theta) is proportional to exp(sum_{v <= k} a (theta - b_v)).
"""
import numpy as np
from scipy.optimize import minimize

Q = 25
NODES = np.linspace(-4, 4, Q)
PRIOR = np.exp(-NODES ** 2 / 2)
PRIOR /= PRIOR.sum()


def probs(a, b, theta):
    """(K, T) probability of each category at each value of theta; b holds the m = K - 1 steps."""
    theta = np.asarray(theta, "float64")
    S = np.concatenate([[0.0], np.cumsum(b)])                     # S_k = sum of the first k steps
    k = np.arange(len(S))
    z = a * (k[:, None] * theta[None, :] - S[:, None])
    z -= z.max(axis=0, keepdims=True)
    P = np.exp(z)
    return P / P.sum(axis=0, keepdims=True)


def _posterior(X, obs, A, B):
    L = np.tile(PRIOR, (len(X), 1))
    for j in range(X.shape[1]):
        m = obs[:, j]
        L[m] *= np.clip(probs(A[j], B[j], NODES), 1e-12, 1)[X[m, j]]
        L[m] /= L[m].sum(axis=1, keepdims=True)
    return L


def _mstep(R, a0, b0):
    """Maximise sum_kq R_kq log P_kq over (log a, b_1..b_m), with the analytic gradient."""
    K = R.shape[0]
    k = np.arange(K)[:, None]
    below = np.arange(1, K)[:, None] <= k.T                       # (m, K): step v enters z_k iff v <= k

    def f(p):
        a, b = np.exp(p[0]), p[1:]
        S = np.concatenate([[0.0], np.cumsum(b)])
        P = probs(a, b, NODES)                                    # (K, Q)
        nll = -(R * np.log(np.clip(P, 1e-300, 1))).sum()
        U = k * NODES[None, :] - S[:, None]                       # dz_k / da
        g_a = -(R * (U - (P * U).sum(axis=0, keepdims=True))).sum() * a
        dz = -a * below                                           # dz_k / db_v, (m, K)
        E = dz @ P                                                # (m, Q)
        g_b = -np.array([(R * (dz[v][:, None] - E[v][None, :])).sum() for v in range(K - 1)])
        return nll, np.concatenate([[g_a], g_b])

    r = minimize(f, np.concatenate([[np.log(a0)], b0]), jac=True, method="L-BFGS-B",
                 options=dict(maxiter=200, ftol=1e-10, gtol=1e-6))
    return np.exp(r.x[0]), r.x[1:]


def fit(X, w, max_iter=60, tol=1e-3, verbose=True):
    """X: (n, J) integer responses starting at 0, -1 = missing. w: calibration weights.

    Returns the discriminations A and the lists of step locations B. The EM loop stops after `max_iter`
    iterations or when no parameter moves by more than `tol`.
    """
    n, J = X.shape
    obs = X >= 0
    K = [int(X[obs[:, j], j].max()) + 1 for j in range(J)]
    A, B = np.ones(J), []
    for j in range(J):                                            # start: logits of the cumulative shares
        v = X[obs[:, j], j]
        cum = np.cumsum(np.bincount(v, minlength=K[j])[::-1])[::-1][1:] / len(v)
        B.append(np.clip(-np.log(cum / (1 - cum)), -3.5, 3.5))
    for it in range(max_iter):
        post = _posterior(X, obs, A, B)                           # E step
        change = 0.0
        for j in range(J):                                        # M step, item by item
            m = obs[:, j]
            R = np.zeros((K[j], Q))
            for k in range(K[j]):
                s = m & (X[:, j] == k)
                R[k] = (post[s] * w[s, None]).sum(axis=0)
            a1, b1 = _mstep(R, A[j], B[j])
            change = max(change, abs(a1 - A[j]), np.abs(b1 - B[j]).max())
            A[j], B[j] = a1, b1
        if verbose:
            print(f"  iteration {it:2d}: largest parameter change {change:.4f}", flush=True)
        if change < tol:
            break
    return A, B


def eap(X, A, B, min_items):
    """Posterior mean under the standard normal prior (NaN below `min_items` valid responses)."""
    obs = X >= 0
    s = _posterior(X, obs, A, B) @ NODES
    return np.where(obs.sum(axis=1) >= min_items, s, np.nan)


def wle(X, A, B, min_items, max_iter=30, tol=1e-6):
    """Warm's weighted likelihood estimate: the theta solving l'(theta) + J(theta) / (2 I(theta)) = 0, with
    I the test information and J its derivative, by Newton's method started at the EAP score.
    NaN below `min_items` valid responses."""
    n, J = X.shape
    obs = X >= 0
    theta = eap(X, A, B, min_items)
    active = np.isfinite(theta)
    theta = np.nan_to_num(theta)
    for it in range(max_iter):
        idx = np.where(active)[0]
        if len(idx) == 0:
            break
        th = theta[idx]
        score, info, dinfo, d2info = (np.zeros(len(idx)) for _ in range(4))
        for j in range(J):
            m = obs[idx, j]
            P = probs(A[j], B[j], th[m])                          # (K, n_m)
            k = np.arange(P.shape[0])[:, None]
            mu = (P * k).sum(axis=0)
            c2, c3, c4 = ((P * (k - mu) ** p).sum(axis=0) for p in (2, 3, 4))
            a = A[j]
            score[m] += a * (X[idx[m], j] - mu)
            info[m] += a ** 2 * c2
            dinfo[m] += a ** 3 * c3
            d2info[m] += a ** 4 * (c4 - 3 * c2 ** 2)
        g = score + dinfo / (2 * info)
        h = -info + (d2info * info - dinfo ** 2) / (2 * info ** 2)
        step = np.clip(-g / h, -1.0, 1.0)
        theta[idx] = np.clip(th + step, -8, 8)
        active[idx[np.abs(step) < tol]] = False
    return np.where(obs.sum(axis=1) >= min_items, theta, np.nan)


def fit_and_score(X, w, min_items, **kw):
    """Calibrate and score in one call: returns (WLE scores, A, B)."""
    A, B = fit(X, w, **kw)
    return wle(X, A, B, min_items), A, B
