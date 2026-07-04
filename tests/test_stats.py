"""
Property/invariant tests for src/stats.py.

These deliberately avoid hardcoding "textbook" critical values that haven't
been independently verified. Instead they check properties that must hold
regardless of the exact numeric constants: rate-matching data shouldn't
reject, wildly-off data should, degenerate inputs (0 obs, 0 exceptions, all
exceptions) shouldn't crash, and clustered exception patterns should score
higher on the independence test than spread-out patterns with the same count.
"""
import numpy as np
import pytest

from stats import kupiec_test, christoffersen_test, basel_zone, basel_multiplier_addon


class TestKupiecTest:
    def test_exact_expected_rate_does_not_reject(self):
        n = 1000
        exc = np.zeros(n, dtype=int)
        exc[:10] = 1  # exactly 1%, matching (1 - var_confidence) for var_confidence=0.99
        result = kupiec_test(exc, var_confidence=0.99)
        assert result["exceptions"] == 10
        assert result["exception_rate"] == pytest.approx(0.01)
        assert result["lr_stat"] == pytest.approx(0.0, abs=1e-6)
        assert result["reject_95"] is False

    def test_high_exception_rate_rejects(self):
        n = 1000
        exc = np.zeros(n, dtype=int)
        exc[:100] = 1  # 10% vs 1% expected -- far too many
        result = kupiec_test(exc, var_confidence=0.99)
        assert result["reject_95"] is True

    def test_zero_observations_does_not_crash(self):
        result = kupiec_test(np.array([]), var_confidence=0.99)
        assert result["n_obs"] == 0
        assert result["exceptions"] == 0
        assert result["lr_stat"] is None
        assert result["reject_95"] is None

    def test_zero_exceptions_does_not_crash(self):
        exc = np.zeros(500, dtype=int)
        result = kupiec_test(exc, var_confidence=0.99)
        assert result["exceptions"] == 0
        assert result["lr_stat"] is not None
        assert np.isfinite(result["lr_stat"])

    def test_all_exceptions_does_not_crash(self):
        exc = np.ones(50, dtype=int)
        result = kupiec_test(exc, var_confidence=0.99)
        assert result["exceptions"] == 50
        assert result["lr_stat"] is not None
        assert np.isfinite(result["lr_stat"])

    def test_lr_stat_always_nonnegative(self):
        n = 500
        for rate in [0.0, 0.005, 0.01, 0.02, 0.5, 1.0]:
            x = int(rate * n)
            exc = np.zeros(n, dtype=int)
            exc[:x] = 1
            result = kupiec_test(exc, var_confidence=0.99)
            assert result["lr_stat"] >= 0


class TestChristoffersenTest:
    def test_single_observation_does_not_crash(self):
        result = christoffersen_test(np.array([1]), var_confidence=0.99)
        assert result["lr_ind"] is None

    def test_empty_does_not_crash(self):
        result = christoffersen_test(np.array([]), var_confidence=0.99)
        assert result["lr_ind"] is None

    def test_no_exceptions_does_not_crash(self):
        exc = np.zeros(300, dtype=int)
        result = christoffersen_test(exc, var_confidence=0.99)
        assert result["lr_ind"] is not None
        assert np.isfinite(result["lr_ind"])

    def test_all_exceptions_does_not_crash(self):
        exc = np.ones(30, dtype=int)
        result = christoffersen_test(exc, var_confidence=0.99)
        assert np.isfinite(result["lr_ind"])

    def test_clustered_exceptions_score_higher_than_spread(self):
        """Same total exception count (20 out of 300), but one contiguous block
        vs. evenly spaced singletons with no adjacent pairs. Clustering means
        exceptions predict each other, which is exactly what lr_ind measures --
        so the clustered pattern must score higher, regardless of the exact
        critical value used to judge significance."""
        n, n_exc = 300, 20

        clustered = np.zeros(n, dtype=int)
        clustered[100:100 + n_exc] = 1

        spread = np.zeros(n, dtype=int)
        positions = np.linspace(0, n - 1, n_exc, dtype=int)
        spread[positions] = 1
        assert np.sum((spread[:-1] == 1) & (spread[1:] == 1)) == 0  # no adjacent pairs

        r_clustered = christoffersen_test(clustered, var_confidence=0.99)
        r_spread = christoffersen_test(spread, var_confidence=0.99)

        assert clustered.sum() == spread.sum() == n_exc
        assert r_clustered["lr_ind"] > r_spread["lr_ind"]

    def test_lr_stats_always_nonnegative(self):
        rng = np.random.default_rng(0)
        exc = (rng.random(500) < 0.05).astype(int)
        result = christoffersen_test(exc, var_confidence=0.99)
        assert result["lr_ind"] >= 0
        assert result["lr_cc"] >= 0


class TestBaselZone:
    def test_boundaries(self):
        assert basel_zone(0) == "green"
        assert basel_zone(4) == "green"
        assert basel_zone(5) == "yellow"
        assert basel_zone(9) == "yellow"
        assert basel_zone(10) == "red"
        assert basel_zone(100) == "red"

    def test_multiplier_zero_in_green(self):
        for c in range(0, 5):
            assert basel_multiplier_addon(c) == 0.0

    def test_multiplier_positive_in_yellow(self):
        for c in range(5, 10):
            assert basel_multiplier_addon(c) > 0.0

    def test_multiplier_capped_in_red(self):
        assert basel_multiplier_addon(10) == 1.0
        assert basel_multiplier_addon(50) == 1.0

    def test_multiplier_monotonic_nondecreasing(self):
        addons = [basel_multiplier_addon(c) for c in range(0, 15)]
        assert all(a <= b for a, b in zip(addons, addons[1:]))
