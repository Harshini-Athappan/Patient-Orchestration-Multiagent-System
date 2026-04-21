"""
run.py — Unified launcher for the Patient Orchestrator system

Handles:
  - Killing any existing processes on the target ports
  - Starting the FastAPI backend
  - Starting the Streamlit UI
  - Graceful shutdown on Ctrl+C
"""

import subprocess
import sys
import time
import socket
import os
import signal

API_PORT = 8004
UI_PORT  = 8502

# ─────────────────────────────────────────────────────────────
# PORT UTILITIES
# ─────────────────────────────────────────────────────────────

def is_port_in_use(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(("localhost", port)) == 0

def kill_port(port: int):
    """Kill whatever process is listening on this port (Windows)."""
    try:
        result = subprocess.run(
            ["netstat", "-ano"],
            capture_output=True, text=True
        )
        for line in result.stdout.splitlines():
            if f":{port}" in line and "LISTENING" in line:
                parts = line.strip().split()
                pid = parts[-1]
                subprocess.run(["taskkill", "/F", "/PID", pid],
                               capture_output=True)
                print(f"  Killed process {pid} on port {port}")
                time.sleep(1)
                return
        print(f"  Port {port} was already free.")
    except Exception as e:
        print(f"  Warning: could not kill port {port}: {e}")

def wait_for_port(port: int, timeout: int = 15) -> bool:
    """Wait until a port is accepting connections."""
    start = time.time()
    while time.time() - start < timeout:
        if is_port_in_use(port):
            return True
        time.sleep(0.5)
    return False

# ─────────────────────────────────────────────────────────────
# MAIN LAUNCHER
# ─────────────────────────────────────────────────────────────

def main():
    python = sys.executable
    root   = os.path.dirname(os.path.abspath(__file__))

    print("=" * 55)
    print("  Patient Orchestrator -- Starting Up")
    print("=" * 55)

    # -- Step 1: Free ports --
    print("\n[1/3] Freeing ports...")
    for port in [API_PORT, UI_PORT]:
        if is_port_in_use(port):
            print(f"  Port {port} is occupied -- killing it...")
            kill_port(port)
        else:
            print(f"  Port {port} is free [OK]")

    # -- Step 2: Start FastAPI backend --
    print(f"\n[2/3] Starting FastAPI backend on http://localhost:{API_PORT} ...")
    api_proc = subprocess.Popen(
        [python, "api.py"],
        cwd=root,
        creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if sys.platform == "win32" else 0
    )

    if wait_for_port(API_PORT, timeout=15):
        print(f"  [OK] API is up at http://localhost:{API_PORT}")
        print(f"     Docs: http://localhost:{API_PORT}/docs")
    else:
        print("  [ERROR] API failed to start within 15s. Check api.py for errors.")
        api_proc.kill()
        sys.exit(1)

    # -- Step 3: Start Streamlit UI --
    print(f"\n[3/3] Starting Streamlit UI on http://localhost:{UI_PORT} ...")
    ui_proc = subprocess.Popen(
        [python, "-m", "streamlit", "run", "app.py",
         "--server.port", str(UI_PORT),
         "--server.headless", "true"],
        cwd=root,
        creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if sys.platform == "win32" else 0
    )

    if wait_for_port(UI_PORT, timeout=20):
        print(f"  [OK] Streamlit UI is up at http://localhost:{UI_PORT}")
    else:
        print("  [ERROR] Streamlit failed to start within 20s.")

    print("\n" + "=" * 55)
    print("  All systems running!")
    print(f"     UI  -> http://localhost:{UI_PORT}")
    print(f"     API -> http://localhost:{API_PORT}")
    print(f"     API Docs -> http://localhost:{API_PORT}/docs")
    print("  Press Ctrl+C to stop everything.")
    print("=" * 55 + "\n")

    # ── Wait and handle Ctrl+C ──
    try:
        api_proc.wait()
    except KeyboardInterrupt:
        print("\n\nShutting down gracefully...")
        api_proc.terminate()
        ui_proc.terminate()
        time.sleep(1)
        print("  Stopped ✓")


if __name__ == "__main__":
    main()
