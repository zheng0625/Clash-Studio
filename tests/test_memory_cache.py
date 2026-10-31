import threading
import time
from concurrent.futures import ThreadPoolExecutor

import pytest

from server.cache import CacheBusy, RevisionCache, estimate_bytes


def blob_cache(**options):
    return RevisionCache(estimate=lambda value: sum(len(part) for part in value['parts']), **options)


def test_byte_budget_evicts_least_recently_used_entries():
    cache = blob_cache(capacity=10, max_bytes=100_000)
    for index in range(5):
        cache.get(('k', index), lambda index=index: {'parts': ['x' * 40_000]})
        if index == 0:
            cache.get(('k', 0), lambda: {'parts': ['uncached']})
    stats = cache.stats()
    assert stats['entries'] <= 2
    assert stats['bytes'] <= 100_000
    assert stats['evictions'] >= 3
    assert stats['method'] == 'retained_size_estimate'


def test_oversized_value_is_returned_without_being_cached():
    cache = blob_cache(capacity=4, max_bytes=8)
    assert cache.get(('a',), lambda: {'parts': ['0123456789']}) == {'parts': ['0123456789']}
    assert cache.get(('a',), lambda: {'parts': ['abcdefghij']}) == {'parts': ['abcdefghij']}
    assert cache.get(('a',), lambda: {'parts': ['fresh']}) == {'parts': ['fresh']}
    stats = cache.stats()
    assert stats['entries'] == 1
    assert stats['oversized'] == 2
    assert stats['hits'] == 0


def test_estimate_tracks_nested_payload_growth():
    assert estimate_bytes({'a': 'x' * 100_000}) > estimate_bytes({'a': 'x'}) + 90_000


def test_single_flight_exception_wakes_every_waiter():
    cache = RevisionCache(capacity=2)
    entered, release = threading.Event(), threading.Event()
    calls = []

    def failing():
        calls.append(1)
        entered.set()
        assert release.wait(2)
        raise RuntimeError('compose failed')

    with ThreadPoolExecutor(6) as pool:
        first = pool.submit(cache.get, ('p', 1), failing)
        assert entered.wait(1)
        rest = [pool.submit(cache.get, ('p', 1), failing) for _ in range(4)]
        release.set()
        for future in (first, *rest):
            with pytest.raises(RuntimeError, match='compose failed'):
                future.result()
    assert len(calls) == 1
    assert cache.stats()['in_flight'] == 0


def test_mutation_isolation_and_hit_copies():
    cache = RevisionCache(capacity=2, estimate=lambda value: 8)
    built = cache.get(('p', 1), lambda: {'nodes': [1]})
    built['nodes'].append(2)
    assert cache.get(('p', 1), lambda: {'nodes': []}) == {'nodes': [1]}
    assert cache.stats()['hits'] == 1


def test_key_budget_bypasses_instead_of_queueing_unbounded_builds():
    cache = RevisionCache(capacity=4, max_keys=1, estimate=lambda value: 8)
    entered, release = threading.Event(), threading.Event()

    def slow():
        entered.set()
        assert release.wait(2)
        return {'value': 'primary'}

    with ThreadPoolExecutor(3) as pool:
        owner = pool.submit(cache.get, ('primary',), slow)
        assert entered.wait(1)
        bypass = pool.submit(cache.get, ('secondary',), lambda: {'value': 'secondary'})
        assert bypass.result() == {'value': 'secondary'}
        assert cache.stats()['bypass'] == 1
        release.set()
        assert owner.result() == {'value': 'primary'}
    assert cache.get(('secondary',), lambda: {'value': 'rebuilt'}) == {'value': 'rebuilt'}


def test_admission_waiters_are_bounded_and_reported():
    cache = RevisionCache(capacity=4, max_builds=1, max_keys=1, max_admission_waiters=2,
                          wait_timeout=2, estimate=lambda value: 8)
    entered, release = threading.Event(), threading.Event()

    def slow():
        entered.set()
        assert release.wait(3)
        return {'value': 'primary'}

    with ThreadPoolExecutor(12) as pool:
        owner = pool.submit(cache.get, ('primary',), slow)
        assert entered.wait(1)
        bypass = [pool.submit(cache.get, ('key', index), lambda index=index: {'value': index})
                  for index in range(10)]
        time.sleep(0.1)
        stats = cache.stats()
        assert stats['admission_waiters'] <= 2
        release.set()
        outcomes = []
        for future in bypass:
            try:
                outcomes.append(future.result())
            except CacheBusy:
                outcomes.append(None)
        assert any(outcome is None for outcome in outcomes)
        assert owner.result() == {'value': 'primary'}
    stats = cache.stats()
    assert stats['admission_waiters'] == 0
    assert stats['max_admission_waiters'] <= 2


def test_same_key_waiters_are_bounded():
    cache = RevisionCache(capacity=4, max_waiters=2, wait_timeout=2, estimate=lambda value: 8)
    entered, release = threading.Event(), threading.Event()

    def slow():
        entered.set()
        assert release.wait(3)
        return {'value': 1}

    with ThreadPoolExecutor(10) as pool:
        owner = pool.submit(cache.get, ('same',), slow)
        assert entered.wait(1)
        waiters = [pool.submit(cache.get, ('same',), slow) for _ in range(6)]
        time.sleep(0.1)
        assert cache.stats()['waiters'] <= 2
        release.set()
        busy = 0
        for future in waiters:
            try:
                assert future.result() == {'value': 1}
            except CacheBusy:
                busy += 1
        assert busy >= 1
        assert owner.result() == {'value': 1}
    assert cache.stats()['waiters'] == 0


def test_same_key_waiter_times_out():
    cache = RevisionCache(capacity=4, max_waiters=4, wait_timeout=0.1, estimate=lambda value: 8)
    entered, release = threading.Event(), threading.Event()

    def slow():
        entered.set()
        assert release.wait(3)
        return {'value': 1}

    with ThreadPoolExecutor(2) as pool:
        owner = pool.submit(cache.get, ('same',), slow)
        assert entered.wait(1)
        with pytest.raises(CacheBusy, match='timed out'):
            cache.get(('same',), slow)
        release.set()
        assert owner.result() == {'value': 1}
