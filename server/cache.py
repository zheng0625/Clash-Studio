"""Small immutable-by-copy single-flight caches, bounded by revision, entries and estimated bytes."""
from collections import OrderedDict
from concurrent.futures import Future, TimeoutError as FutureTimeoutError
from copy import deepcopy
from sys import getsizeof
from threading import BoundedSemaphore, Lock

DEFAULT_CAPACITY = 8
DEFAULT_MAX_BYTES = 32 * 1024 * 1024
DEFAULT_MAX_BUILDS = 2
DEFAULT_MAX_KEYS = 4
DEFAULT_MAX_WAITERS = 16
DEFAULT_MAX_ADMISSION_WAITERS = 8
DEFAULT_WAIT_TIMEOUT = 30.0


class CacheBusy(RuntimeError):
    """Raised when the cache refuses or times out a blocking admission."""


def estimate_bytes(value, max_nodes=1_000_000):
    """Cheap approximate retained size for JSON-like values.

    The result is an estimate for cache budgeting only; it is not the exact
    Python heap footprint. Shared sub-objects are counted once.
    """
    total = nodes = 0
    seen = set()
    stack = [value]
    while stack and nodes < max_nodes:
        item = stack.pop()
        nodes += 1
        total += getsizeof(item)
        if isinstance(item, dict):
            for key, child in item.items():
                total += getsizeof(key)
                if id(child) not in seen:
                    seen.add(id(child))
                    stack.append(child)
        elif isinstance(item, (list, tuple, set, frozenset)):
            for child in item:
                if id(child) not in seen:
                    seen.add(id(child))
                    stack.append(child)
    return total


class RevisionCache:
    """LRU cache with single-flight builds and byte/entry budgets.

    - Same key: one build, all callers get independent deep copies.
    - Oversized values are returned but never cached.
    - Distinct concurrent builds and registered keys are bounded; when the
      key budget is exhausted new builds pass through without caching.
    """

    def __init__(self, capacity=DEFAULT_CAPACITY, max_bytes=DEFAULT_MAX_BYTES,
                 max_builds=DEFAULT_MAX_BUILDS, max_keys=DEFAULT_MAX_KEYS, estimate=estimate_bytes,
                 max_waiters=DEFAULT_MAX_WAITERS, max_admission_waiters=DEFAULT_MAX_ADMISSION_WAITERS,
                 wait_timeout=DEFAULT_WAIT_TIMEOUT):
        self.capacity = max(1, int(capacity))
        self.max_bytes = max(0, int(max_bytes))
        self.max_keys = max(1, int(max_keys))
        self.max_waiters = max(0, int(max_waiters))
        self.max_admission_waiters = max(0, int(max_admission_waiters))
        self.wait_timeout = max(0.0, float(wait_timeout))
        self.estimate = estimate
        self.lock = Lock()
        self.build_slots = BoundedSemaphore(max(1, int(max_builds)))
        self.values = OrderedDict()
        self.pending = {}
        self.bytes = 0
        self.hits = self.misses = 0
        self.evictions = self.oversized = self.bypass = 0
        self.waiters = 0
        self.max_waiters_seen = 0
        self.admission_waiters = 0
        self.max_admission_waiters_seen = 0

    def get(self, key, build):
        owner = bypass = False
        with self.lock:
            if key in self.values:
                self.hits += 1
                self.values.move_to_end(key)
                return deepcopy(self.values[key][0])
            future = self.pending.get(key)
            if future is not None:
                if self.waiters >= self.max_waiters:
                    raise CacheBusy('cache waiter limit reached')
                self.waiters += 1
                self.max_waiters_seen = max(self.max_waiters_seen, self.waiters)
            else:
                owner = True
                if len(self.pending) >= self.max_keys:
                    self.bypass += 1
                    bypass = True
                else:
                    self.misses += 1
                    future = self.pending[key] = Future()
        if not owner:
            try:
                try:
                    return deepcopy(future.result(timeout=self.wait_timeout))
                except FutureTimeoutError:
                    raise CacheBusy('cache wait timed out') from None
            finally:
                with self.lock:
                    self.waiters -= 1
        if bypass:
            return self._build_bounded(build)
        try:
            value = self._build_bounded(build)
            self._store(key, value)
            future.set_result(value)
            return deepcopy(value)
        except BaseException as error:
            future.set_exception(error)
            raise
        finally:
            with self.lock:
                self.pending.pop(key, None)

    def _build_bounded(self, build):
        with self.lock:
            if self.admission_waiters >= self.max_admission_waiters:
                raise CacheBusy('cache build queue busy')
            self.admission_waiters += 1
            self.max_admission_waiters_seen = max(self.max_admission_waiters_seen, self.admission_waiters)
        try:
            if not self.build_slots.acquire(timeout=self.wait_timeout):
                raise CacheBusy('cache build wait timed out')
            try:
                return build()
            finally:
                self.build_slots.release()
        finally:
            with self.lock:
                self.admission_waiters -= 1

    def _store(self, key, value):
        size = self.estimate(value)
        with self.lock:
            if size > self.max_bytes:
                self.oversized += 1
                return
            previous = self.values.pop(key, None)
            if previous is not None:
                self.bytes -= previous[1]
            self.values[key] = (value, size)
            self.bytes += size
            while self.values and (len(self.values) > self.capacity or self.bytes > self.max_bytes):
                _, (_, evicted_size) = self.values.popitem(last=False)
                self.bytes -= evicted_size
                self.evictions += 1

    def clear(self):
        with self.lock:
            self.values.clear()
            self.bytes = 0

    def stats(self):
        with self.lock:
            return dict(entries=len(self.values), bytes=self.bytes, capacity=self.capacity,
                        max_bytes=self.max_bytes, in_flight=len(self.pending), hits=self.hits,
                        misses=self.misses, evictions=self.evictions, oversized=self.oversized,
                        bypass=self.bypass, waiters=self.waiters, max_waiters=self.max_waiters_seen,
                        admission_waiters=self.admission_waiters,
                        max_admission_waiters=self.max_admission_waiters_seen,
                        wait_timeout=self.wait_timeout, max_waiter_limit=self.max_waiters,
                        max_admission_limit=self.max_admission_waiters,
                        method='retained_size_estimate')
