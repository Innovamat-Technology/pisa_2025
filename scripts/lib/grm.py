"""Single-factor graded response model: marginal maximum likelihood by EM on a fixed grid, EAP scores."""
import numpy as np
from scipy.optimize import minimize

Q = 25
NODES = np.linspace(-4, 4, Q)
PRIOR = np.exp(-NODES ** 2 / 2)
PRIOR /= PRIOR.sum()


def _probs(a, b):
    """(K, Q) probability of each response category at each node."""
    z = a * (NODES[None, :] - b[:, None])
    P = 1 / (1 + np.exp(-z))                                   # P(X >= k), k = 1..K-1
    P = np.vstack([np.ones((1, Q)), P, np.zeros((1, Q))])
    return np.clip(P[:-1] - P[1:], 1e-9, 1.0)


def _posterior(X, obs, A, B):
    L = np.tile(PRIOR, (len(X), 1))
    for j in range(X.shape[1]):
        m = obs[:, j]
        L[m] *= _probs(A[j], B[j])[X[m, j]]
        L[m] /= L[m].sum(axis=1, keepdims=True)
    return L


def fit_and_score(X, w, min_items, max_iter=40, tol=1e-3, verbose=True):
    """X: (n, J) integer responses starting at 0, -1 = missing. w: calibration weights.

    Returns EAP scores (NaN below `min_items` valid responses), discriminations and thresholds.
    The EM loop stops after `max_iter` iterations or when no parameter moves by more than `tol`.
    """
    n, J = X.shape
    obs = X >= 0
    K = [int(X[obs[:, j], j].max()) + 1 for j in range(J)]
    A, B = np.ones(J), []
    for j in range(J):
        v = X[obs[:, j], j]
        cum = np.cumsum(np.bincount(v, minlength=K[j])[::-1])[::-1][1:] / len(v)
        B.append(np.clip(-np.log(cum / (1 - cum)), -3.5, 3.5))
    for it in range(max_iter):
        post = _posterior(X, obs, A, B)
        change = 0.0
        for j in range(J):
            m = obs[:, j]
            R = np.zeros((K[j], Q))
            for k in range(K[j]):
                s = m & (X[:, j] == k)
                R[k] = (post[s] * w[s, None]).sum(axis=0)

            def nll(p):
                return -(R * np.log(_probs(np.exp(p[0]), np.sort(p[1:])))).sum()

            r = minimize(nll, np.concatenate([[np.log(A[j])], B[j]]), method="Powell",
                         options=dict(maxiter=4000, xtol=1e-3, ftol=1e-4))
            a1, b1 = np.exp(r.x[0]), np.sort(r.x[1:])
            change = max(change, abs(a1 - A[j]), np.abs(b1 - B[j]).max())
            A[j], B[j] = a1, b1
        if verbose:
            print(f"  iteration {it:2d}: largest parameter change {change:.4f}", flush=True)
        if change < tol:
            break
    eap = _posterior(X, obs, A, B) @ NODES
    return np.where(obs.sum(axis=1) >= min_items, eap, np.nan), A, B
