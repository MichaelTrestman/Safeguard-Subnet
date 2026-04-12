"""Tests for PROBES_PER_MINER_PER_CYCLE dispatch scaling.

Pins the property that raising `PROBES_PER_MINER_PER_CYCLE` linearly
scales the number of probes sent per miner per cycle, WITHOUT
requiring the operator to scale UID count. This is the validator-side
throughput fix for the UID-sharding antipattern: each miner can earn
additively across the N probes it's given per cycle, so one capable
miner at N=10 produces 10x the contribution of the same miner at N=1,
and operators don't have to stack UIDs to scale data throughput.

Run:
    python manage.py test tests.test_dispatch_probes_per_miner
"""
from __future__ import annotations

import asyncio
from unittest import mock

from django.test import TransactionTestCase

from validator import loop as vloop
from validator.models import Concern, RegisteredTarget


class _FakeWallet:
    """Minimal wallet stand-in. `_send_probe_to_miner` is mocked, so
    the wallet's hotkey/sign methods are never actually invoked; the
    dispatch function just needs a non-None object to pass through."""


class _FakeMetagraph:
    """Fake metagraph with a `.hotkeys` list long enough to cover the
    test UIDs. The dispatch function only reads `.hotkeys[uid]` to
    stamp the hotkey on the result dict; no other attributes used."""

    def __init__(self, n: int):
        self.hotkeys = [f"hk_{i}" for i in range(n)]


def _make_target() -> RegisteredTarget:
    return RegisteredTarget.objects.create(
        client_hotkey="5FakeClient",
        name="probe-target-scaling",
        relay_endpoint="https://example.test/relay",
        subnet_type="llm-chat",
        categories=["throughput-test"],
    )


def _seed_concerns(n: int) -> None:
    for i in range(n):
        Concern.objects.create(
            id_slug=f"throughput-concern-{i}",
            title=f"Throughput concern {i}",
            concern_text=f"A test concern #{i}.",
            category="throughput-test",
            severity_prior=0.5,
            active=True,
        )


class ProbesPerMinerScalingTests(TransactionTestCase):
    # TransactionTestCase (not TestCase) because `_dispatch_target_to_miners`
    # uses `sync_to_async` to query active concerns, same reason
    # test_hitl_dispatch uses it — sqlite under sync_to_async worker
    # threads can't see the outer TestCase transaction.

    def setUp(self):
        self.target = _make_target()
        _seed_concerns(3)
        self.wallet = _FakeWallet()
        self.metagraph = _FakeMetagraph(200)
        self.probe_miners = {
            100: "http://miner-100.test",
            101: "http://miner-101.test",
            102: "http://miner-102.test",
        }

    def _run(self, coro):
        # Fresh loop per test — matches test_hitl_dispatch pattern.
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(coro)
        finally:
            loop.close()

    def _run_dispatch(self, n: int) -> tuple[tuple[int, list[dict]], int]:
        """Patch `PROBES_PER_MINER_PER_CYCLE=n` and `_send_probe_to_miner`,
        run the dispatch, return ((n_dispatched, results), n_send_calls).
        The mock counts how many times `_send_probe_to_miner` was
        actually invoked so the test can distinguish "n_dispatched is
        right but the fanout never happened" from "everything fanned
        out correctly."""
        call_count = {"n": 0}

        async def fake_send(
            client, wallet, endpoint, task_id, target_ep,
            category, concern_id_slug, client_hotkey="",
        ):
            call_count["n"] += 1
            return {
                "transcript": [],
                "miner_safety_score": 0.0,
                "task_id_echo": task_id,
            }

        semaphore = asyncio.Semaphore(16)
        with mock.patch.object(vloop, "PROBES_PER_MINER_PER_CYCLE", n), \
             mock.patch.object(vloop, "_send_probe_to_miner", side_effect=fake_send):
            result = self._run(vloop._dispatch_target_to_miners(
                self.wallet, self.target, self.probe_miners,
                self.metagraph, semaphore,
            ))
        return result, call_count["n"]

    def test_n1_legacy_one_probe_per_miner(self):
        """Default N=1 preserves legacy throughput: one probe per miner."""
        (n_dispatched, results), n_calls = self._run_dispatch(1)
        self.assertEqual(n_dispatched, 3)  # 3 miners × 1 probe
        self.assertEqual(n_calls, 3)
        self.assertEqual(len(results), 3)

    def test_n5_five_probes_per_miner(self):
        """N=5 scales throughput linearly: five probes per miner."""
        (n_dispatched, results), n_calls = self._run_dispatch(5)
        self.assertEqual(n_dispatched, 15)  # 3 miners × 5 probes
        self.assertEqual(n_calls, 15)
        self.assertEqual(len(results), 15)

    def test_n10_fan_out_uid_distribution(self):
        """Every eligible miner UID appears exactly N times in the results
        list. No UID starvation, no preferential allocation — this is
        the "protocol invariant: all eligible miners get the same work"
        property at scale."""
        (_, results), _ = self._run_dispatch(10)
        uid_counts = {100: 0, 101: 0, 102: 0}
        for r in results:
            uid_counts[r["uid"]] += 1
        self.assertEqual(uid_counts, {100: 10, 101: 10, 102: 10})

    def test_task_ids_are_unique_within_cycle(self):
        """Each of the N probes per miner mints its own task_id; no
        collisions within a cycle. Required because task_id is the
        Evaluation primary key."""
        (_, results), _ = self._run_dispatch(5)
        task_ids = [r["task_id"] for r in results]
        self.assertEqual(
            len(task_ids), len(set(task_ids)),
            f"Duplicate task_ids within single cycle: {task_ids}",
        )

    def test_empty_catalog_returns_zero_without_fanning_out(self):
        """If the concern catalog is empty, no probes get dispatched
        regardless of N. Guards against a bug where N=10 × empty
        catalog still fires 10 no-op probes."""
        Concern.objects.all().delete()
        (n_dispatched, results), n_calls = self._run_dispatch(5)
        self.assertEqual(n_dispatched, 0)
        self.assertEqual(n_calls, 0)
        self.assertEqual(results, [])
