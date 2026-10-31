"""Bounded process output and diagnostics without exception messages or locals."""
from datetime import datetime, timezone
import json
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
import threading
import traceback


class FailureLog:
    def __init__(self, path, max_bytes=2 * 1024 * 1024, backups=2):
        self.handler = RotatingFileHandler(path, maxBytes=max_bytes, backupCount=backups,
                                           encoding='utf-8', delay=True)

    def record(self, error, operation_id, kind):
        errors, seen = [], set()
        while error is not None and id(error) not in seen and len(errors) < 6:
            seen.add(id(error))
            frames = traceback.extract_tb(error.__traceback__)[-32:]
            # Deliberately omit error messages, source lines, arguments and locals:
            # any of them can contain subscription credentials or request bodies.
            errors.append({'type': type(error).__name__, 'frames': [
                {'file': Path(frame.filename).name, 'function': frame.name, 'line': frame.lineno}
                for frame in frames]})
            error = error.__cause__ or (None if error.__suppress_context__ else error.__context__)
        value = {'time': datetime.now(timezone.utc).isoformat(), 'operation_id': operation_id,
                 'kind': kind, 'errors': errors}
        self.handler.handle(logging.makeLogRecord({'msg': json.dumps(value, ensure_ascii=False), 'levelno': logging.ERROR}))

    def close(self):
        self.handler.close()


class ProcessLog:
    """Drain a child's pipe continuously, keeping at most three 4 MiB files."""
    def __init__(self, path, max_bytes=4 * 1024 * 1024, backups=2, on_error=None):
        self.path, self.max_bytes, self.backups = Path(path), max_bytes, backups
        self.thread = None
        self.on_error = on_error
        self.failed = False
        # Preserve the recent tail when upgrading an installation with a large log.
        if self.path.exists() and self.path.stat().st_size > max_bytes:
            with self.path.open('rb') as previous:
                previous.seek(-max_bytes, 2)
                tail = previous.read(max_bytes)
            self.path.write_bytes(tail)
        self.output = self.path.open('ab', buffering=0)
        self.size = self.path.stat().st_size

    def attach(self, stream):
        if stream is None:
            self.close()
            return
        def drain():
            try:
                read = getattr(stream, 'read1', stream.read)
                while chunk := read(65536):
                    if self.failed:
                        continue
                    try:
                        self.write(chunk)
                    except OSError:
                        self.failed = True
                        if self.on_error:
                            try:
                                self.on_error()
                            except Exception:
                                pass
                        # Continue consuming output even if disk writes fail;
                        # logging must never block a running proxy core.
            finally:
                stream.close()
                self.output.close()
        self.thread = threading.Thread(target=drain, daemon=True, name='core-log')
        try:
            self.thread.start()
        except Exception:
            self.thread = None
            stream.close()
            self.output.close()
            raise

    def write(self, chunk):
        while chunk:
            if self.size >= self.max_bytes:
                self.output.close()
                for index in range(self.backups, 0, -1):
                    source = self.path if index == 1 else self.path.with_name(self.path.name + f'.{index - 1}')
                    destination = self.path.with_name(self.path.name + f'.{index}')
                    if source.exists():
                        source.replace(destination)
                self.output = self.path.open('wb', buffering=0)
                self.size = 0
            count = min(len(chunk), self.max_bytes - self.size)
            written = self.output.write(chunk[:count])
            if not written:
                raise OSError('Log write did not advance')
            self.size += written
            chunk = chunk[written:]

    def close(self):
        if self.thread is not None:
            self.thread.join(timeout=1)
        else:
            self.output.close()
