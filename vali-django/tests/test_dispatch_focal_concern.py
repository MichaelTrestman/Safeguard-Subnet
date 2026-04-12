"""Tests for the direct-concern dispatch picker (`_pick_focal_concern`).

The dispatcher picks a focal Concern per probe, alternating 50/50 between
severity-weighted random and uniform random. These tests verify:

  1. Empty catalog returns None.
  2. Single-concern catalog always returns that concern.
  3. Over 300 trials with three concerns at severity_prior 0.0 / 0.5 / 1.0,
     the distribution is ordered (high > mid > low) and the low-severity
     concern still gets a non-trivial floor share (>= 10% of picks) thanks
     to the uniform branch — this is the "zero-severity concerns never
     fully starve" property.
"""
from collections import Counter

from django.test import SimpleTestCase


class PickFocalConcernTests(SimpleTestCase):
    def test_empty_catalog_returns_none(self):
        from validator.loop import _pick_focal_concern
        self.assertIsNone(_pick_focal_concern([]))

    def test_single_concern_always_returned(self):
        from validator.loop import _pick_focal_concern
        only = {"id_slug": "only", "category": "x", "severity_prior": 0.5}
        for _ in range(50):
            self.assertEqual(_pick_focal_concern([only])["id_slug"], "only")

    def test_distribution_is_ordered_with_floor(self):
        """High > mid > low, and low has >= 10% of total picks."""
        import random

        from validator.loop import _pick_focal_concern

        random.seed(1337)  # deterministic for repeatability
        concerns = [
            {"id_slug": "low", "category": "c", "severity_prior": 0.0},
            {"id_slug": "mid", "category": "c", "severity_prior": 0.5},
            {"id_slug": "high", "category": "c", "severity_prior": 1.0},
        ]
        n_trials = 300
        c = Counter(
            _pick_focal_concern(concerns)["id_slug"] for _ in range(n_trials)
        )

        # Every concern should have been picked at least once.
        self.assertGreater(c["low"], 0, f"low got 0 picks in {n_trials} trials")
        self.assertGreater(c["mid"], 0, f"mid got 0 picks in {n_trials} trials")
        self.assertGreater(c["high"], 0, f"high got 0 picks in {n_trials} trials")

        # Ordering: high > mid > low.
        self.assertGreater(
            c["high"], c["mid"],
            f"expected high>mid but got high={c['high']} mid={c['mid']} low={c['low']}",
        )
        self.assertGreater(
            c["mid"], c["low"],
            f"expected mid>low but got high={c['high']} mid={c['mid']} low={c['low']}",
        )

        # Floor property: the zero-severity concern still gets >= 10% of
        # picks because the uniform branch fires 50% of the time and
        # picks uniformly over all three concerns — expected ~16.6%.
        low_share = c["low"] / n_trials
        self.assertGreaterEqual(
            low_share, 0.10,
            f"expected low_share >= 10% but got {low_share:.3f} "
            f"(c={dict(c)}) — zero-severity concerns are starving",
        )

    def test_all_zero_severity_falls_back_to_uniform(self):
        """If every concern has severity_prior == 0, the weighted branch
        computes a total weight of 0 and falls through to uniform. No
        divide-by-zero, no crash, uniform distribution over all concerns."""
        import random

        from validator.loop import _pick_focal_concern

        random.seed(99)
        concerns = [
            {"id_slug": "a", "category": "c", "severity_prior": 0.0},
            {"id_slug": "b", "category": "c", "severity_prior": 0.0},
        ]
        c = Counter(
            _pick_focal_concern(concerns)["id_slug"] for _ in range(200)
        )
        # Roughly balanced (tolerant bound)
        self.assertGreater(c["a"], 50)
        self.assertGreater(c["b"], 50)
