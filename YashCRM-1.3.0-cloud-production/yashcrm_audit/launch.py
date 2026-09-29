#!/usr/bin/env python3
"""Start Yash CRM with one command: sets up a private environment on first run, starts the
server, and opens the app in your browser.

    python launch.py              # local only (recommended)
    python launch.py --port 8080
    python launch.py --lan        # also reachable from other devices on your network
    python launch.py --no-browser
"""
from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import time
import venv
import webbrowser
from pathlib import Path
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parent
VENV = ROOT / ".venv"

# Python versions this app is tested on. Newer releases often break pinned dependencies
# (Python 3.14 crashed SQLAlchemy 2.0.36), so anything outside this range is not used blindly.
MIN_VERSION = (3, 10)
MAX_VERSION = (3, 12)
PREFERRED_MINORS = (12,)  # order in which other installed Pythons are tried


def venv_python() -> Path:
    return VENV / ("Scripts/python.exe" if os.name == "nt" else "bin/python")


def supported(version: tuple[int, int]) -> bool:
    return version == (3, 12)


def interpreter_version(path: str | Path) -> tuple[int, int] | None:
    try:
        out = subprocess.check_output([str(path), "-c", "import sys; print(sys.version_info[0], sys.version_info[1])"], text=True, timeout=20)
        major, minor = out.split()[:2]
        return int(major), int(minor)
    except (OSError, ValueError, subprocess.SubprocessError):
        return None


def find_supported_python() -> str | None:
    """Look for an installed Python inside the tested range, best match first."""
    for minor in PREFERRED_MINORS:
        if not supported((3, minor)):
            continue
        candidates: list[str] = []
        if os.name == "nt":
            try:  # the Windows "py" launcher knows every installed version
                out = subprocess.check_output(["py", f"-3.{minor}", "-c", "import sys; print(sys.executable)"], text=True, stderr=subprocess.DEVNULL, timeout=20)
                candidates.append(out.strip())
            except (OSError, subprocess.SubprocessError):
                pass
        found = shutil.which(f"python3.{minor}")
        if found:
            candidates.append(found)
        for candidate in candidates:
            if candidate and interpreter_version(candidate) == (3, minor):
                return candidate
    return None


def ensure_supported_python() -> None:
    """Re-run under a supported Python if this one is too old or too new."""
    if supported(sys.version_info[:2]):
        return
    have = ".".join(map(str, sys.version_info[:3]))
    wanted = "3.12"
    better = find_supported_python() if not os.getenv("YASHCRM_REEXEC") else None
    if better:
        print(f"Python {have} is outside the supported range ({wanted}); using {better} instead.")
        os.environ["YASHCRM_REEXEC"] = "1"
        sys.exit(subprocess.call([better, str(Path(__file__).resolve()), *sys.argv[1:]]))
    sys.exit(
        f"Yash CRM supports Python {wanted}, and you have {have}, with no other supported version found.\n"
        "Install Python 3.12 from https://www.python.org/downloads/ (it can sit alongside the version you have) and run this again."
    )


def ensure_environment() -> Path:
    ensure_supported_python()
    python = venv_python()
    if python.exists() and not supported(interpreter_version(python) or (0, 0)):
        print("The private environment was built with an unsupported Python. Rebuilding it...")
        shutil.rmtree(VENV, ignore_errors=True)
    if not python.exists():
        print("Setting up a private Python environment (first run only)...")
        venv.EnvBuilder(with_pip=True).create(VENV)
    requirements = ROOT / "requirements.txt"
    stamp = VENV / ".requirements-stamp"
    wanted = requirements.read_text()
    if not stamp.exists() or stamp.read_text() != wanted:
        print("Installing dependencies. This needs an internet connection and only happens when requirements change...")
        subprocess.check_call([str(python), "-m", "pip", "install", "--quiet", "--disable-pip-version-check", "-r", str(requirements)])
        stamp.write_text(wanted)
    return python


def wait_for_health(url: str, process: subprocess.Popen | None, timeout: float = 40.0) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        if process is not None and process.poll() is not None:
            return False
        try:
            with urlopen(f"{url}/health", timeout=2) as response:
                if response.status == 200:
                    return True
        except OSError:
            time.sleep(0.4)
    return False


def main() -> int:
    parser = argparse.ArgumentParser(description="Run Yash CRM")
    parser.add_argument("--port", type=int, default=int(os.getenv("PORT", "3000")))
    parser.add_argument("--lan", action="store_true", help="listen on all network interfaces (there is no login, so only use on a trusted network)")
    parser.add_argument("--no-browser", action="store_true", help="do not open a browser window")
    args = parser.parse_args()

    python = ensure_environment()
    host = "0.0.0.0" if args.lan else "127.0.0.1"
    url = f"http://yashcrm.local:{args.port}"
    command = [str(python), "-m", "uvicorn", "app.main:app", "--host", host, "--port", str(args.port)]
    process = subprocess.Popen(command, cwd=ROOT)
    try:
        if not wait_for_health(url, process):
            if process.poll() is not None:
                print(f"\nThe server stopped during startup. Is port {args.port} already in use? Try: python launch.py --port {args.port + 1}")
            else:
                print("\nThe server did not become ready in time. Check the messages above.")
            process.terminate()
            return 1
        data = os.getenv("DATABASE_URL") or f"{ROOT / 'yashcrm.db'}"
        print(f"\nYash CRM is running at {url}\nData: {data}\nPress Ctrl+C to stop.\n")
        if args.lan:
            print("LAN mode: anyone on your network can open this app and edit your data.\n")
        if not args.no_browser:
            webbrowser.open(url)
        return process.wait()
    except KeyboardInterrupt:
        print("\nStopping Yash CRM...")
        process.terminate()
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()
        return 0


if __name__ == "__main__":
    sys.exit(main())
