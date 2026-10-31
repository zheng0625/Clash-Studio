"""Bounded, observable lifecycle jobs; cancellation is intent, not premature cleanup."""
import contextvars
import copy
import secrets
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from fastapi import HTTPException
from .contracts import envelope

operation_id = contextvars.ContextVar('clash_operation_id', default=None)
cancelled = contextvars.ContextVar('clash_operation_cancelled', default=None)


class Operations:
    def __init__(self, capacity=4, failures=None):
        self.failures = failures
        self.executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix='clash-lifecycle')
        self.slots = threading.BoundedSemaphore(capacity)
        self.lock = threading.RLock()
        self.jobs = {}
        self.closed = False

    def submit(self, kind, function, cancel=None):
        if self.closed or not self.slots.acquire(blocking=False):
            raise HTTPException(429, '操作队列已满，请稍后重试')
        key = secrets.token_hex(12)
        job = dict(operation_id=key, kind=kind, phase='queued', accepted_at=time.time(), cancel_requested=False)
        with self.lock:
            self.jobs[key] = [job, None, cancel]
        def run():
            token = operation_id.set(key)
            cancel_token = cancelled.set(lambda: job['cancel_requested'])
            try:
                with self.lock:
                    if job['cancel_requested']:
                        job['phase'] = 'cancelled'
                        return
                    job.update(phase='running', started_at=time.time())
                result = function()
                with self.lock:
                    job.update(phase='succeeded', result=result)
            except Exception as error:
                if self.failures:
                    self.failures.record(error, key, kind)
                with self.lock:
                    failure = envelope(getattr(error, 'status_code', 500), getattr(error, 'detail', '操作未完成，请查看运行诊断'), key)['error']
                    if job['cancel_requested']:
                        failure.update(code='OPERATION_CANCELLED', message='操作已取消')
                    job.update(phase='cancelled' if job['cancel_requested'] else 'failed', error=failure)

            finally:
                with self.lock:
                    job['finished_at'] = time.time()
                cancelled.reset(cancel_token)
                operation_id.reset(token)
        try:
            future = self.executor.submit(run)
            with self.lock:
                self.jobs[key][1] = future
            def done(_):
                self.slots.release()
                with self.lock:
                    if future.cancelled():
                        job.update(phase='cancelled', finished_at=time.time())
                    terminal = [k for k, (j, _, _) in self.jobs.items() if j['phase'] in ('succeeded', 'failed', 'cancelled')]
                    for old in terminal[:-64]:
                        self.jobs.pop(old, None)
            future.add_done_callback(done)
            return self.get(key)
        except BaseException:
            self.slots.release()
            with self.lock:
                self.jobs.pop(key, None)
            raise

    def get(self, key):
        with self.lock:
            if key not in self.jobs:
                raise HTTPException(404, '操作记录不存在或已过期')
            return copy.deepcopy(self.jobs[key][0])

    def cancel(self, key):
        callback = None
        with self.lock:
            job, future, callback = self.jobs.get(key, (None, None, None))
            if job is None:
                raise HTTPException(404, '操作记录不存在或已过期')
            if job['phase'] in ('queued', 'running'):
                job['cancel_requested'] = True
                if future is not None and future.cancel():
                    callback = None
            else:
                callback = None
        if callback:
            callback(key)
        return self.get(key)

    def cancel_applies(self):
        with self.lock:
            keys = [key for key, (job, _, _) in self.jobs.items() if job['kind'] == 'apply' and job['phase'] in ('queued', 'running')]
        for key in keys:
            self.cancel(key)

    def stats(self):
        with self.lock:
            jobs = [dict(item[0]) for item in self.jobs.values()]
        waits = sorted((j['started_at'] - j['accepted_at']) * 1000 for j in jobs if 'started_at' in j)
        def percentile(p):
            return round(waits[min(len(waits) - 1, int((len(waits) - 1) * p))], 2) if waits else None
        return dict(queued=sum(j['phase'] == 'queued' for j in jobs), running=sum(j['phase'] == 'running' for j in jobs),
                    retained=len(jobs), queue_wait_ms=dict(p50=percentile(.5), p95=percentile(.95)))

    def close(self):
        self.closed = True
        self.cancel_applies()
        self.executor.shutdown(wait=False, cancel_futures=True)
