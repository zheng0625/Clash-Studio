"""Unprivileged watchdog: reap the capability-enabled core if its backend dies."""
import ctypes
import os
from pathlib import Path
import signal
import subprocess
import time


def run_core(args):
    if len(args) != 4:
        raise SystemExit('Invalid Linux core invocation')
    parent, binary, directory, candidate = args
    parent = int(parent)
    directory, candidate = Path(directory).resolve(), Path(candidate).resolve()
    if candidate.parent != directory or not candidate.name.startswith('candidate-') or candidate.suffix != '.yaml':
        raise SystemExit('Invalid Linux core configuration')
    stopping = False

    def stop(signum, frame):
        nonlocal stopping
        stopping = True

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    # Set on the unprivileged watchdog, not on the file-capability executable
    # (Linux clears PDEATHSIG when executing such a binary).
    libc = ctypes.CDLL(None, use_errno=True)
    if libc.prctl(1, signal.SIGTERM, 0, 0, 0) != 0:
        raise OSError(ctypes.get_errno(), 'Cannot arm core parent-death guard')
    if os.getppid() != parent or stopping:
        return
    process = subprocess.Popen([binary, '-d', str(directory), '-f', str(candidate)])
    try:
        while process.poll() is None and not stopping and os.getppid() == parent:
            time.sleep(.1)
    finally:
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(3)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
    raise SystemExit(process.returncode)


if __name__ == '__main__':
    import sys
    run_core(sys.argv[1:])
