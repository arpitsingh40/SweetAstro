"""
SweetAstro Chat Server.
Launches the chat-first FastAPI app (Consumer Astrology Answer Engine).

Every start runs strict preflight checks first and ABORTS when a critical
requirement is missing (DeepSeek key/reachability, Swiss Ephemeris, chart
self-test, port availability). Run checks only with:

    python serve.py --check

Configuration (optional environment variables / .env):
    SWEETASTRO_HOST=127.0.0.1    bind address (0.0.0.0 for LAN access)
    SWEETASTRO_PORT=8088         listening port

For background start/stop/status use the helper:  .\\server.ps1 start
"""

import os
import sys
from pathlib import Path

# Add project directory to Python path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Keep chat history + structured kundali across restarts by default.
# Set CHAT_PERSIST=0 in the environment to disable. Must be set before the
# SweetAstro config module loads.
os.environ.setdefault("CHAT_PERSIST", "1")

HOST = os.environ.get("SWEETASTRO_HOST", "127.0.0.1")
PORT = int(os.environ.get("SWEETASTRO_PORT", "8088"))


def main() -> int:
    from SweetAstro.src.chat.preflight import run_preflight

    check_only = "--check" in sys.argv
    reload_mode = "--reload" in sys.argv or os.environ.get("SWEETASTRO_RELOAD") == "1"
    ok, already_running = run_preflight(HOST, PORT, verbose=True)

    if already_running:
        return 0
    if not ok:
        return 1
    if check_only:
        return 0

    import uvicorn

    shown_host = "127.0.0.1" if HOST in ("0.0.0.0", "::") else HOST
    print()
    print("==================================================================")
    print("  SweetAstro -- Consumer Astrology Answer Engine (chat)          ")
    print(f"  Chat UI:    http://{shown_host}:{PORT}                          ")
    print(f"  API Docs:   http://{shown_host}:{PORT}/docs                     ")
    if reload_mode:
        print("  DEV MODE:   auto-reload ON (backend edits restart the server)  ")
        print("              static UI edits need no restart — just refresh     ")
    print("==================================================================")
    uvicorn.run("SweetAstro.src.api.app:app", host=HOST, port=PORT, reload=reload_mode)
    return 0


if __name__ == "__main__":
    sys.exit(main())
