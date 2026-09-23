"""
TradeCore Terminal — PyWebView masaüstü başlatıcısı (.exe uyumlu).

Ne yapar?
1) FastAPI (:5080) ayakta değilse sessizce (konsolsuz) başlatır.
2) Next.js (:3010) ayakta değilse sessizce başlatır.
3) Servisler hazır olunca adres çubuğu olmayan koyu masaüstü penceresi açar.

PyInstaller notu:
- `sys.frozen` True ise exe `dist/TradeCore.exe` içindedir; proje kökü bir üst dizindir.
- API için her zaman `server/.venv` Python'u kullanılır (exe kendini uvicorn olarak çalıştıramaz).
"""

from __future__ import annotations

import atexit
import os
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

# Windows'ta alt süreçleri siyah konsol penceresi açmadan çalıştırır.
CREATE_NO_WINDOW = 0x08000000 if os.name == "nt" else 0


def resolve_root() -> Path:
    """
    Proje kök dizinini bulur.

    - Geliştirme: desktop.py'nin bulunduğu klasör
    - Paketlenmiş exe: dist/ içindeki exe için bir üst klasör (TradeCore/)
    """
    if getattr(sys, "frozen", False):
        exe_dir = Path(sys.executable).resolve().parent
        if exe_dir.name.lower() == "dist":
            return exe_dir.parent
        return exe_dir
    return Path(__file__).resolve().parent


ROOT = resolve_root()
SERVER_DIR = ROOT / "server"
FRONTEND_DIR = ROOT / "frontend"
VENV_PYTHON = SERVER_DIR / ".venv" / "Scripts" / "python.exe"
API_HOST = "127.0.0.1"
API_PORT = 5080
WEB_HOST = "127.0.0.1"
WEB_PORT = 3010
WEB_URL = f"http://{WEB_HOST}:{WEB_PORT}/dashboard"

_managed: list[subprocess.Popen] = []


def port_open(host: str, port: int) -> bool:
    """TCP portu dinleniyor mu?"""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.4)
        return sock.connect_ex((host, port)) == 0


def http_ok(url: str, timeout: float = 1.5) -> bool:
    """HTTP 2xx/3xx yanıtı geliyor mu?"""
    try:
        with urllib.request.urlopen(url, timeout=timeout) as response:
            return 200 <= getattr(response, "status", 200) < 400
    except (urllib.error.URLError, TimeoutError, OSError):
        return False


def wait_until(predicate, label: str, timeout: float = 120.0) -> None:
    """predicate True olana kadar bekler; süre dolarsa RuntimeError."""
    started = time.time()
    while time.time() - started < timeout:
        if predicate():
            return
        time.sleep(0.6)
    raise RuntimeError(f"{label} {timeout:.0f}s icinde hazir olmadi.")


def start_api() -> None:
    """FastAPI'yi konsolsuz uvicorn ile başlatır (port doluysa dokunmaz)."""
    if port_open(API_HOST, API_PORT):
        return

    if not VENV_PYTHON.exists():
        raise RuntimeError(f"Sanal ortam bulunamadi: {VENV_PYTHON}")

    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT)
    process = subprocess.Popen(
        [
            str(VENV_PYTHON),
            "-m",
            "uvicorn",
            "server.main:app",
            "--host",
            API_HOST,
            "--port",
            str(API_PORT),
        ],
        cwd=str(ROOT),
        env=env,
        creationflags=CREATE_NO_WINDOW,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    _managed.append(process)


def start_frontend() -> None:
    """Next.js'i 3010'da konsolsuz başlatır (port doluysa dokunmaz)."""
    if port_open(WEB_HOST, WEB_PORT):
        return

    npm = "npm.cmd" if os.name == "nt" else "npm"
    process = subprocess.Popen(
        [npm, "run", "dev", "--", "-p", str(WEB_PORT)],
        cwd=str(FRONTEND_DIR),
        creationflags=CREATE_NO_WINDOW,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    _managed.append(process)


def cleanup() -> None:
    """Pencere kapanınca bu exe'nin açtığı çocuk süreçleri sonlandırır."""
    for process in _managed:
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=4)
            except subprocess.TimeoutExpired:
                process.kill()


def main() -> None:
    """TradeCore Terminal penceresini açar."""
    atexit.register(cleanup)

    start_api()
    wait_until(lambda: http_ok(f"http://{API_HOST}:{API_PORT}/health"), "FastAPI")

    start_frontend()
    wait_until(lambda: http_ok(WEB_URL) or http_ok(f"http://{WEB_HOST}:{WEB_PORT}"), "Next.js")

    try:
        import webview
    except ImportError as exc:
        raise SystemExit(
            "pywebview yuklu degil. server\\.venv\\Scripts\\pip install pywebview"
        ) from exc

    webview.create_window(
        "TradeCore Terminal",
        WEB_URL,
        width=1400,
        height=900,
        background_color="#09090b",
        text_select=True,
    )
    webview.start()


if __name__ == "__main__":
    main()
