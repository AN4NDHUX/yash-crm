"""Desktop entry point for Yash CRM (this is what YashCRM.exe runs).

Starts the server on this computer and opens the app in its own window. Your data is kept in
yashcrm.db next to the program. Closing the console window quits the app.
Also works unpackaged:  python yashcrm_app.py
"""
from __future__ import annotations

import os
import shutil
import socket
import subprocess
import sys
import threading
import time
import webbrowser
from pathlib import Path
from urllib.request import urlopen

FIRST_PORT = int(os.getenv("PORT", "3000"))


def data_dir() -> Path:
    if getattr(sys, "frozen", False) and os.name == "nt":
        root = Path(os.getenv("LOCALAPPDATA", Path.home() / "AppData" / "Local")) / "YashCRM" / "data"
        root.mkdir(parents=True, exist_ok=True)
        return root
    return Path(__file__).resolve().parent


def port_is_free(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        return sock.connect_ex(("127.0.0.1", port)) != 0


def yash_crm_running(port: int) -> bool:
    try:
        with urlopen(f"http://127.0.0.1:{port}/health", timeout=1.5) as response:
            return response.status == 200 and b"yash-crm" in response.read()
    except OSError:
        return False


def browser_command(url: str) -> list[str] | None:
    """Edge or Chrome in app mode gives a clean window without tabs or an address bar."""
    roots = [os.getenv(name) for name in ("PROGRAMFILES(X86)", "PROGRAMFILES", "LOCALAPPDATA")]
    candidates = [Path(root) / rel for root in roots if root for rel in ("Microsoft/Edge/Application/msedge.exe", "Google/Chrome/Application/chrome.exe")]
    candidates += [Path(found) for name in ("msedge", "chrome", "google-chrome", "chromium") if (found := shutil.which(name))]
    for path in candidates:
        if path.exists():
            return [str(path), f"--app={url}"]
    return None


def open_window(url: str) -> None:
    command = browser_command(url)
    if command:
        try:
            subprocess.Popen(command)
            return
        except OSError:
            pass
    webbrowser.open(url)


def main() -> int:
    base = data_dir()
    os.chdir(base)
    os.environ.setdefault("DATABASE_URL", f"sqlite:///{(base / 'yashcrm.db').as_posix()}")

    if yash_crm_running(FIRST_PORT):          # already started: just open another window
        open_window(f"http://yashcrm.local:{FIRST_PORT}")
        return 0
    port = next((candidate for candidate in range(FIRST_PORT, FIRST_PORT + 20) if port_is_free(candidate)), None)
    if port is None:
        print(f"No free port found between {FIRST_PORT} and {FIRST_PORT + 19}.")
        return 1

    import uvicorn
    from app.main import app

    url = f"http://yashcrm.local:{port}"
    print(f"Yash CRM is running at {url}\nData: {base / 'yashcrm.db'}\nClose this window to quit.\n")
    threading.Thread(target=lambda: (time.sleep(1.2), open_window(url)), daemon=True).start()
    uvicorn.run(app, host="127.0.0.1", port=port, log_level="warning")
    return 0


if __name__ == "__main__":
    sys.exit(main())
