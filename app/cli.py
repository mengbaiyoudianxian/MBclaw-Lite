"""mbclaw CLI — one-command install & launch, just like OpenClaw.

Usage:
    mbclaw onboard          Interactive setup wizard
    mbclaw start            Start gateway daemon (foreground)
    mbclaw start --daemon   Start as background daemon
    mbclaw stop             Stop running daemon
    mbclaw status           Show daemon status
    mbclaw agent -m "..."   One-shot agent query
    mbclaw chat             Interactive chat mode
    mbclaw doctor           System health check
    mbclaw version          Print version
"""

import argparse
import os
import signal
import subprocess
import sys
import time
from pathlib import Path


APP_DIR = Path(__file__).resolve().parent.parent
PID_FILE = Path.home() / ".mbclaw" / "gateway.pid"
LOG_FILE = Path.home() / ".mbclaw" / "gateway.log"
DEFAULT_PORT = 8000
VERSION = "0.1.0"


# ═══════════════════════════════════════════════════════════════
# helpers
# ═══════════════════════════════════════════════════════════════

def _ensure_dir():
    Path.home().joinpath(".mbclaw").mkdir(parents=True, exist_ok=True)


def _is_running() -> bool:
    if not PID_FILE.exists():
        return False
    try:
        pid = int(PID_FILE.read_text().strip())
        os.kill(pid, 0)
        return True
    except (OSError, ValueError):
        PID_FILE.unlink(missing_ok=True)
        return False


def _api(path: str, method: str = "GET", data: dict = None) -> dict:
    import urllib.request, json as _json
    url = f"http://127.0.0.1:{DEFAULT_PORT}{path}"
    req = urllib.request.Request(url, method=method)
    req.add_header("Content-Type", "application/json")
    if data:
        req.data = _json.dumps(data).encode()
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return _json.loads(resp.read())
    except Exception:
        return {"error": f"Cannot reach mbclaw gateway on port {DEFAULT_PORT}"}


# ═══════════════════════════════════════════════════════════════
# commands
# ═══════════════════════════════════════════════════════════════

def cmd_onboard():
    """Interactive setup wizard."""
    print("🦞 MBclaw v" + VERSION)
    print()
    config = {}
    config["port"] = input(f"  Gateway port [{DEFAULT_PORT}]: ").strip() or str(DEFAULT_PORT)
    config["api_key"] = input("  LLM API key (or Enter for mock mode): ").strip()
    config["model"] = input("  LLM model [gpt-4o-mini]: ").strip() or "gpt-4o-mini"
    config["auto_start"] = input("  Auto-start on boot? [y/N]: ").strip().lower() == "y"

    _ensure_dir()
    import json
    cfg_path = Path.home() / ".mbclaw" / "config.json"
    cfg_path.write_text(json.dumps(config, indent=2))
    print(f"\n  ✅ Config saved to {cfg_path}")
    print(f"  Run 'mbclaw start' to launch the gateway.")


def cmd_start(daemon: bool = False):
    """Start gateway."""
    if _is_running():
        print("Gateway is already running.")
        return

    _ensure_dir()
    env = os.environ.copy()
    env["MBCLAW_LLM_MOCK"] = "1"

    cfg_path = Path.home() / ".mbclaw" / "config.json"
    if cfg_path.exists():
        import json
        cfg = json.loads(cfg_path.read_text())
        if cfg.get("api_key"):
            env["MBCLAW_LLM_API_KEY"] = cfg["api_key"]
            env["MBCLAW_LLM_MOCK"] = "0"
        env["MBCLAW_LLM_MODEL"] = cfg.get("model", "gpt-4o-mini")
        port = cfg.get("port", str(DEFAULT_PORT))
    else:
        port = str(DEFAULT_PORT)

    if daemon:
        log = open(LOG_FILE, "a")
        proc = subprocess.Popen(
            [sys.executable, "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", port],
            cwd=str(APP_DIR), env=env, stdout=log, stderr=log,
            start_new_session=True,
        )
        PID_FILE.write_text(str(proc.pid))
        time.sleep(1)
        if _is_running():
            print(f"🦞 Gateway started (pid {proc.pid}) on port {port}")
        else:
            print("Failed to start. Check log: ~/.mbclaw/gateway.log")
    else:
        print(f"🦞 Starting gateway on port {port}...")
        os.execve(sys.executable, [sys.executable, "-m", "uvicorn", "app.main:app",
                                    "--host", "0.0.0.0", "--port", port], env)


def cmd_stop():
    """Stop running daemon."""
    if not _is_running():
        print("No gateway running.")
        return
    pid = int(PID_FILE.read_text().strip())
    os.kill(pid, signal.SIGTERM)
    PID_FILE.unlink(missing_ok=True)
    print("Gateway stopped.")


def cmd_status():
    """Show daemon status."""
    if _is_running():
        pid = int(PID_FILE.read_text().strip())
        print(f"🦞 Gateway RUNNING (pid {pid}) on port {DEFAULT_PORT}")
        health = _api("/health")
        print(f"  DB: {'OK' if health.get('db_ok') else 'FAIL'}")
        metrics = _api("/metrics")
        if "sessions_created" in metrics:
            print(f"  Sessions: {metrics['sessions_created']} created / {metrics['sessions_closed']} closed")
            print(f"  Search hit rate: {metrics.get('search_hit_rate', 'N/A')}")
    else:
        print("Gateway STOPPED.")


def cmd_agent(message: str):
    """One-shot agent query."""
    if not _is_running():
        print("Gateway not running. Start with 'mbclaw start' first.")
        return
    result = _api("/agent/run", "POST", {"message": message})
    if "error" in result:
        print(result["error"])
    else:
        print(result.get("response", str(result)))


def cmd_chat():
    """Interactive chat mode."""
    if not _is_running():
        print("Gateway not running. Start with 'mbclaw start' first.")
        return
    print("🦞 MBclaw Chat (type /exit to quit)")
    sid = None
    while True:
        try:
            msg = input("\nYou: ")
        except (EOFError, KeyboardInterrupt):
            print("\nBye.")
            break
        if msg.lower() in ("/exit", "/quit"):
            break
        result = _api("/agent/run", "POST", {"message": msg})
        if "error" in result:
            print(f"Error: {result['error']}")
        else:
            print(f"MBclaw: {result.get('response', '')}")


def cmd_doctor():
    """System health check."""
    print("🦞 MBclaw Doctor")
    print(f"  Version: {VERSION}")
    print(f"  Python:  {sys.version}")
    print(f"  PID file: {PID_FILE}")
    print(f"  Running: {_is_running()}")

    # Check dependencies
    deps_ok = True
    for mod in ("fastapi", "uvicorn", "sqlalchemy", "jieba", "httpx"):
        try:
            __import__(mod)
            print(f"  {mod}: ✅")
        except ImportError:
            print(f"  {mod}: ❌ not installed")
            deps_ok = False

    if not deps_ok:
        print("\n  Run: pip install mbclaw")


# ═══════════════════════════════════════════════════════════════
# main
# ═══════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(description="MBclaw — Personal AI Assistant")
    sub = parser.add_subparsers(dest="command")

    sub.add_parser("onboard", help="Interactive setup wizard")

    p_start = sub.add_parser("start", help="Start gateway")
    p_start.add_argument("--daemon", action="store_true", help="Run as background daemon")

    sub.add_parser("stop", help="Stop gateway daemon")
    sub.add_parser("status", help="Show gateway status")
    sub.add_parser("doctor", help="System health check")
    sub.add_parser("version", help="Print version")

    p_agent = sub.add_parser("agent", help="One-shot agent query")
    p_agent.add_argument("-m", "--message", required=True, help="Message to send")

    sub.add_parser("chat", help="Interactive chat mode")

    args = parser.parse_args()

    if args.command == "onboard":
        cmd_onboard()
    elif args.command == "start":
        cmd_start(daemon=args.daemon)
    elif args.command == "stop":
        cmd_stop()
    elif args.command == "status":
        cmd_status()
    elif args.command == "agent":
        cmd_agent(args.message)
    elif args.command == "chat":
        cmd_chat()
    elif args.command == "doctor":
        cmd_doctor()
    elif args.command == "version":
        print(f"mbclaw v{VERSION}")
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
