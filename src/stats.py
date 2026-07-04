"""
Backtesting statistics for VaR models: Kupiec proportion-of-failures (POF)
test and the Christoffersen independence / conditional coverage tests.

Pure functions, no file I/O -- kept separate from analysis.py specifically
so they're easy to unit test (see tests/test_stats.py).
"""
import numpy as np
from scipy import stats


def kupiec_test(exceptions, var_confidence: float = 0.99) -> dict:
    """Unconditional coverage test: does the exception rate match (1 - VaR confidence)?"""
    exceptions = np.asarray(exceptions)
    p = 1 - var_confidence
    x = int(np.sum(exceptions))
    n_obs = len(exceptions)
    if n_obs == 0:
        return dict(exceptions=0, n_obs=0, exception_rate=None, expected_rate=p,
                    lr_stat=None, p_value=None, reject_95=None)

    phat = x / n_obs

    def loglik(prob, x, n):
        if x == 0:
            return (n - x) * np.log(1 - prob)
        if x == n:
            return x * np.log(prob)
        return (n - x) * np.log(1 - prob) + x * np.log(prob)

    ll_null = loglik(p, x, n_obs)
    ll_alt = loglik(phat, x, n_obs)
    lr_stat = max(-2 * (ll_null - ll_alt), 0.0)
    p_value = 1 - stats.chi2.cdf(lr_stat, df=1)

    return dict(
        exceptions=x, n_obs=n_obs, exception_rate=phat, expected_rate=p,
        lr_stat=lr_stat, p_value=p_value, reject_95=bool(p_value < 0.05),
    )


def christoffersen_test(exceptions, var_confidence: float = 0.99) -> dict:
    """Independence test (do exceptions cluster?) plus combined conditional coverage."""
    exc = np.asarray(exceptions)
    n_obs = len(exc)
    if n_obs < 2:
        return dict(lr_ind=None, p_value_ind=None, lr_cc=None, p_value_cc=None)

    prev, curr = exc[:-1], exc[1:]
    n00 = int(np.sum((prev == 0) & (curr == 0)))
    n01 = int(np.sum((prev == 0) & (curr == 1)))
    n10 = int(np.sum((prev == 1) & (curr == 0)))
    n11 = int(np.sum((prev == 1) & (curr == 1)))

    def safe_term(count, prob):
        if count == 0 or prob <= 0 or prob >= 1:
            return 0.0
        return count * np.log(prob)

    pi01 = n01 / (n00 + n01) if (n00 + n01) > 0 else 0.0
    pi11 = n11 / (n10 + n11) if (n10 + n11) > 0 else 0.0
    pi = (n01 + n11) / (n00 + n01 + n10 + n11) if (n00 + n01 + n10 + n11) > 0 else 0.0

    ll_restricted = safe_term(n00 + n10, 1 - pi) + safe_term(n01 + n11, pi)
    ll_unrestricted = (
        safe_term(n00, 1 - pi01) + safe_term(n01, pi01)
        + safe_term(n10, 1 - pi11) + safe_term(n11, pi11)
    )
    lr_ind = max(-2 * (ll_restricted - ll_unrestricted), 0.0)
    p_value_ind = 1 - stats.chi2.cdf(lr_ind, df=1)

    kt = kupiec_test(exc, var_confidence)
    lr_cc = lr_ind + (kt["lr_stat"] or 0.0)
    p_value_cc = 1 - stats.chi2.cdf(lr_cc, df=2)

    return dict(
        n00=n00, n01=n01, n10=n10, n11=n11,
        lr_ind=lr_ind, p_value_ind=p_value_ind, reject_ind_95=bool(p_value_ind < 0.05),
        lr_cc=lr_cc, p_value_cc=p_value_cc, reject_cc_95=bool(p_value_cc < 0.05),
    )


def basel_zone(breach_count_250d: int) -> str:
    if breach_count_250d <= 4:
        return "green"
    if breach_count_250d <= 9:
        return "yellow"
    return "red"


def basel_multiplier_addon(breach_count_250d: int) -> float:
    if breach_count_250d <= 4:
        return 0.0
    scale = {5: 0.4, 6: 0.5, 7: 0.65, 8: 0.75, 9: 0.85}
    return scale.get(breach_count_250d, 1.0)
