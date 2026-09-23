from __future__ import annotations
import json
from pathlib import Path

VERSION = "1.0.1"
PLUGIN_ID = "cmd-orchestrator"

STATE_ROOT = Path.home() / ".hermes" / "state" / PLUGIN_ID
RUN_DB = STATE_ROOT / "orchestrator.sqlite3"
LEARN_DB = STATE_ROOT / "learning.sqlite3"
CURRENT_JSON = STATE_ROOT / "current.json"
RUNS_DIR = STATE_ROOT / "runs"
RESCUE_DIR = STATE_ROOT / "rescue"
SETTINGS_JSON = STATE_ROOT / "settings.json"

DEFAULT_SETTINGS = {
    "version": VERSION,
    "mode": "balanced",
    "auto": "review",
    "max_depth": 2,
    "max_parallel": 3,
    "checkpoint_every_tool": True,
    "fm_rescue": True,
    "routing_policy": "cost_first_verified",
    "models": {
        "emergency_local": {"provider": "local", "model": "fm", "cost": "local"},
        "cheap_fast": {"provider": "commandcode", "model": "auto-cheap", "cost": "low"},
        "balanced": {"provider": "commandcode", "model": "auto-balanced", "cost": "medium"},
        "strong": {"provider": "commandcode", "model": "auto-strong", "cost": "high"}
    }
}

def ensure_dirs():
    STATE_ROOT.mkdir(parents=True, exist_ok=True)
    RUNS_DIR.mkdir(parents=True, exist_ok=True)
    RESCUE_DIR.mkdir(parents=True, exist_ok=True)

def load_settings():
    ensure_dirs()
    if not SETTINGS_JSON.exists():
        save_settings(DEFAULT_SETTINGS.copy())
        return DEFAULT_SETTINGS.copy()
    try:
        data = json.loads(SETTINGS_JSON.read_text(encoding="utf-8"))
    except Exception:
        data = {}
    merged = DEFAULT_SETTINGS.copy()
    merged.update(data if isinstance(data, dict) else {})
    merged["version"] = VERSION
    return merged

def save_settings(data):
    ensure_dirs()
    tmp = SETTINGS_JSON.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(SETTINGS_JSON)
