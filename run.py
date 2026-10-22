"""Run the isolated Windows alpha from the existing project's Python runtime."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import threading
import time
import urllib.request
import webbrowser

HOME = Path(__file__).resolve().parent
sys.dont_write_bytecode = True
sys.path.insert(0, str(HOME / "vendor"))
sys.path.insert(0, str(HOME))
os.environ["CLASH_STUDIO_DATA"] = str(HOME / "data")
(HOME / "data").mkdir(parents=True, exist_ok=True)
if sys.stdout is None:
    sys.stdout = sys.stderr = (HOME / "data" / "launcher.log").open("a", encoding="utf-8", buffering=1)
LOCAL = urllib.request.build_opener(urllib.request.ProxyHandler({}))
INSTANCE = hashlib.sha256(str(HOME).casefold().encode()).hexdigest()[:16]


def is_ours(url):
    try:
        with LOCAL.open(url + "/api/client/info", timeout=1) as response:
            info = json.load(response)
        return info.get("app") == "clash-studio-alpha" and info.get("instance") == INSTANCE
    except (OSError, ValueError):
        return False


def open_window(url):
    for _ in range(80):
        if is_ours(url):
            edge = Path(os.environ.get("ProgramFiles(x86)", "C:/Program Files (x86)")) / "Microsoft/Edge/Application/msedge.exe"
            if edge.exists():
                subprocess.Popen([str(edge), f"--app={url}", f"--user-data-dir={HOME / 'data' / 'edge-profile'}",
                                  "--no-first-run", "--window-size=1360,940"], creationflags=subprocess.CREATE_NO_WINDOW)
            else:
                webbrowser.open(url)
            return
        time.sleep(0.25)


def main():
    if len(sys.argv) > 1 and sys.argv[1] == "--core-helper":
        from server.elevation import run_helper
        run_helper(HOME, sys.argv[2:])
        return
    parser = argparse.ArgumentParser(description="Clash Studio Windows Alpha")
    parser.add_argument("--port", type=int, default=8870)
    parser.add_argument("--no-window", action="store_true")
    parser.add_argument("--desktop", action="store_true", help="Backend owned by the Tauri desktop process")
    parser.add_argument("--stop", action="store_true")
    parser.add_argument("--restore-proxy", action="store_true")
    args = parser.parse_args()
    if args.restore_proxy:
        from server.proxy import SystemProxy
        print(json.dumps(SystemProxy(HOME / "data").restore(), ensure_ascii=False))
        return
    if not 1024 <= args.port <= 65535:
        parser.error("port must be between 1024 and 65535")
    url = f"http://127.0.0.1:{args.port}"
    if args.stop:
        if not is_ours(url):
            raise SystemExit("This alpha installation is not running on the selected port.")
        request = urllib.request.Request(url + "/api/shutdown", method="POST", data=b"{}",
                                         headers={"X-Clash-Studio": "1", "Content-Type": "application/json"})
        with LOCAL.open(request, timeout=12):
            print("Stopping alpha backend and its core; restoring owned system proxy.")
        return
    with socket.socket() as probe:
        try:
            probe.bind(("127.0.0.1", args.port))
        except OSError:
            if is_ours(url):
                if not args.no_window:
                    open_window(url)
                return
            raise SystemExit(f"Port {args.port} belongs to another application. Use --port.")
    if not args.no_window:
        threading.Thread(target=open_window, args=(url,), daemon=True).start()
    import uvicorn
    from server.api import build_app
    app = build_app(HOME)
    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=args.port, access_log=False))
    app.state.shutdown_callback = lambda: setattr(server, "should_exit", True)
    print(f"Clash Studio Alpha: {url}")
    server.run()


if __name__ == "__main__":
    main()
