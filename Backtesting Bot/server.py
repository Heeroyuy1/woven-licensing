"""Harper Server — Lightweight HTTP API for dashboard re-run requests."""
import asyncio
import json
import logging
import os
import subprocess
import sys
import threading
from pathlib import Path
from datetime import datetime

from flask import Flask, request, jsonify, send_from_directory

PROJECT_ROOT = Path(__file__).resolve().parent
os.chdir(str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT))

logging.basicConfig(level=logging.INFO, format="%(asctime)s [Harper.Server] %(message)s")
logger = logging.getLogger("Harper.Server")

app = Flask(__name__)

# Status tracking
_run_status = {"running": False, "last_run": None, "error": None, "symbols": [], "progress": ""}


@app.route("/")
def serve_dashboard():
    """Serve the dashboard HTML with aggressive cache-busting."""
    dashboard_path = PROJECT_ROOT / "reports" / "dashboard.html"
    if not dashboard_path.exists():
        return "Dashboard not found. Run python main.py first.", 404
    html = dashboard_path.read_text(encoding="utf-8")
    response = app.response_class(html, mimetype="text/html")
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate, max-age=0"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    response.headers["Last-Modified"] = "Thu, 01 Jan 1970 00:00:00 GMT"
    return response


@app.route("/<path:filename>")
def serve_static(filename):
    """Serve static files from the reports directory (e.g. harper-logo.png)."""
    reports_dir = PROJECT_ROOT / "reports"
    file_path = reports_dir / filename
    if file_path.exists() and file_path.is_file():
        return send_from_directory(str(reports_dir), filename)
    return "File not found", 404


@app.route("/api/status")
def api_status():
    return jsonify(_run_status)


@app.route("/api/run", methods=["POST"])
def api_run():
    """Trigger a Harper backtest run with custom symbols."""
    if _run_status["running"]:
        return jsonify({"error": "Already running", "status": _run_status}), 409

    data = request.get_json() or {}
    symbols_str = data.get("symbols", "")
    
    if not symbols_str.strip():
        return jsonify({"error": "No symbols provided"}), 400

    symbols = [s.strip().upper() for s in symbols_str.split(",") if s.strip()]
    initial_capital = float(data.get("initial_capital", 100000))
    strategy_config = data.get("strategy", {})
    start_date = data.get("start_date") or "2020-01-01"
    end_date = data.get("end_date") or "2025-12-31"
    allow_shorts = data.get("allow_shorts", True)

    # Merge with existing config
    config = _load_config()
    config["symbols"] = symbols
    config["initial_capital"] = initial_capital
    config["start_date"] = start_date
    config["end_date"] = end_date
    config["strategy"] = strategy_config
    config["allow_shorts"] = allow_shorts
    _save_config(config)

    _run_status["running"] = True
    _run_status["symbols"] = symbols
    _run_status["error"] = None
    _run_status["last_run"] = datetime.now().isoformat()
    _run_status["progress"] = f"Starting Harper for {', '.join(symbols)}..."

    # Run in background thread
    thread = threading.Thread(target=_run_harper_background, daemon=True)
    thread.start()

    return jsonify({"ok": True, "symbols": symbols, "message": "Harper started"})


def _load_config():
    config_path = PROJECT_ROOT / "config" / "backtest_config.json"
    if config_path.exists():
        with open(config_path) as f:
            return json.load(f)
    return {"symbols": ["AAPL"], "start_date": "2020-01-01", "end_date": "2025-12-31", "interval": "1d"}


def _save_config(config):
    config_path = PROJECT_ROOT / "config" / "backtest_config.json"
    config_path.parent.mkdir(exist_ok=True)
    with open(config_path, "w") as f:
        json.dump(config, f, indent=2)


def _run_harper_background():
    """Run python main.py as a subprocess, capture output."""
    try:
        _run_status["progress"] = "Fetching data & running backtest..."
        env = os.environ.copy()
        env["PYTHONIOENCODING"] = "utf-8"
        result = subprocess.run(
            [sys.executable, str(PROJECT_ROOT / "main.py")],
            capture_output=True, text=True, timeout=300,
            cwd=str(PROJECT_ROOT), env=env,
            encoding="utf-8", errors="replace",
        )
        if result.returncode == 0:
            _run_status["progress"] = "Complete — dashboard ready"
            _run_status["error"] = None
            logger.info("Harper run complete")
        else:
            # Parse stderr for the real error (might be encoding-related)
            stderr_clean = result.stderr or ""
            stdout_clean = result.stdout or ""
            # If stdout contains "Harper analysis complete", it actually succeeded
            if "Harper analysis complete" in stdout_clean:
                _run_status["progress"] = "Complete — dashboard ready"
                _run_status["error"] = None
                logger.info("Harper run complete (non-zero exit from encoding, ignored)")
            else:
                _run_status["error"] = stderr_clean[-500:] or "Unknown error"
                _run_status["progress"] = "Error — check logs"
                logger.error(f"Harper failed: {_run_status['error']}")
    except subprocess.TimeoutExpired:
        _run_status["error"] = "Timeout (5 min)"
        _run_status["progress"] = "Timeout"
    except Exception as e:
        _run_status["error"] = str(e)
        _run_status["progress"] = "Error"
    finally:
        _run_status["running"] = False


if __name__ == "__main__":
    logger.info("Harper Server starting on http://localhost:5000")
    print("\n" + "=" * 60)
    print("  HARPER SERVER")
    print("  http://localhost:5000")
    print("=" * 60)
    print("  Open in browser → http://localhost:5000")
    print("  Type custom symbols → click Run Harper → auto reloads")
    print("=" * 60 + "\n")
    app.run(host="127.0.0.1", port=5000, debug=False)
