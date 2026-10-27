"""Small immutable-by-copy single-flight caches, bounded by revision and capacity."""
from collections import OrderedDict
from concurrent.futures import Future
from copy import deepcopy
from threading import Lock


class RevisionCache:
    def __init__(self, capacity=16):
        self.capacity = capacity
        self.lock = Lock()
        self.values = OrderedDict()
        self.pending = {}
        self.hits = self.misses = 0

    def get(self, key, build):
        with self.lock:
            if key in self.values:
                self.hits += 1
                self.values.move_to_end(key)
                return deepcopy(self.values[key])
            future = self.pending.get(key)
            owner = future is None
            if owner:
                self.misses += 1
                future = self.pending[key] = Future()
        if not owner:
            return deepcopy(future.result())
        try:
            value = build()
            with self.lock:
                self.values[key] = deepcopy(value)
                while len(self.values) > self.capacity:
                    self.values.popitem(last=False)
            future.set_result(value)
            return deepcopy(value)
        except BaseException as error:
            future.set_exception(error)
            raise
        finally:
            with self.lock:
                self.pending.pop(key, None)

    def stats(self):
        with self.lock:
            return dict(entries=len(self.values), in_flight=len(self.pending), hits=self.hits, misses=self.misses)
