import os
from pathlib import Path
import sys

HOME = Path(__file__).resolve().parents[1]
sys.dont_write_bytecode = True
sys.path.insert(0, str(HOME))
sys.path.insert(0, str(HOME / "vendor"))
os.environ["CLASH_STUDIO_DATA"] = str(HOME / "artifacts" / "import-data")


def free_mixed_port():
    import secrets
    import socket
    # TCP and UDP ephemeral allocators can repeatedly choose ranges reserved
    # for the other protocol on Windows. Probe both in the user port range.
    for _ in range(1000):
        port = 20000 + secrets.randbelow(29000)
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as udp, socket.socket() as tcp:
            try:
                udp.bind(('127.0.0.1', port))
                tcp.bind(('127.0.0.1', port))
                return port
            except OSError:
                continue
    raise RuntimeError('No loopback TCP/UDP port available')
