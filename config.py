from __future__ import annotations
import json
from pathlib import Path

VERSION = "1.3.1"
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
    "auto": "review",
    "mode": "balanced",  # compatibility only; Hermes owns routing in v1.2
    "routing_owner": "hermes",
    "role_routing": True,
    "planner_requires_strong_reasoning": True,
    "planner_preferred_models": ["sol", "deepseek-v4-pro"],
    "scout_preferred_models": ["muse-spark-1.3-contributor"],
    "coder_policy": "cheapest_capable_after_algorithm_contract",
    "secretary_policy": "interaction_only_no_architecture_authority",
    "simple_path": "hermes_direct",
    "grill_for_substantial": True,
    "require_prompt_review": True,
    "require_plan_review": True,
    "plan_resolution": "task/work_unit/step",
    "max_parallel": 3,
    "atomic_code_unit": "function_or_method",
    "library_first": True,
    "forbid_library_reimplementation": True,
    "parallel_independent_units": True,
    "checkpoint_every_tool": True,
    "fm_rescue": True,
    "learning_review": True,
    # Kept for backward compatibility and emergency fallback only.
    "models": {
        "emergency_local": {"provider": "local", "model": "fm", "cost": "local"},
        "cheap_fast": {"provider": "commandcode", "model": "auto-cheap", "cost": "low"},
        "balanced": {"provider": "commandcode", "model": "auto-balanced", "cost": "medium"},
        "strong": {"provider": "commandcode", "model": "auto-strong", "cost": "high"},
    },
}

def ensure_dirs():
    STATE_ROOT.mkdir(parents=True, exist_ok=True)
    RUNS_DIR.mkdir(parents=True, exist_ok=True)
    RESCUE_DIR.mkdir(parents=True, exist_ok=True)

def load_settings():
    ensure_dirs()
    if not SETTINGS_JSON.exists():
        data = dict(DEFAULT_SETTINGS)
        save_settings(data)
        return data
    try:
        data = json.loads(SETTINGS_JSON.read_text(encoding="utf-8"))
    except Exception:
        data = {}
    merged = dict(DEFAULT_SETTINGS)
    if isinstance(data, dict):
        merged.update(data)
    merged["version"] = VERSION
    merged["routing_owner"] = "hermes"
    return merged

def save_settings(data):
    ensure_dirs()
    data = dict(data)
    data["version"] = VERSION
    data["routing_owner"] = "hermes"
    tmp = SETTINGS_JSON.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(SETTINGS_JSON)

def hermes_model_catalog():
    """Best-effort provider/model inventory using Hermes' own config and catalog."""
    providers = set()
    current_provider = ""
    current_model = ""
    try:
        from hermes_cli.config import load_config_readonly
        cfg = load_config_readonly() or {}
        model = cfg.get("model", {}) if isinstance(cfg, dict) else {}
        if isinstance(model, dict):
            current_provider = str(model.get("provider") or "").strip()
            current_model = str(model.get("default") or model.get("model") or "").strip()
            if current_provider:
                providers.add(current_provider)
        pmap = cfg.get("providers", {}) if isinstance(cfg, dict) else {}
        if isinstance(pmap, dict):
            providers.update(str(x).strip() for x in pmap if str(x).strip())
        custom = cfg.get("custom_providers", []) if isinstance(cfg, dict) else []
        if isinstance(custom, list):
            for item in custom:
                if isinstance(item, dict) and str(item.get("name") or "").strip():
                    providers.add("custom:" + str(item["name"]).strip())
    except Exception:
        pass
    try:
        from hermes_cli.model_switch import get_authenticated_provider_slugs
        import inspect
        sig = inspect.signature(get_authenticated_provider_slugs)
        kwargs = {}
        if "current_provider" in sig.parameters:
            kwargs["current_provider"] = current_provider
        result = get_authenticated_provider_slugs(**kwargs)
        if isinstance(result, (list, tuple, set)):
            providers.update(str(x).strip() for x in result if str(x).strip())
    except Exception:
        pass

    rows = {}
    for provider in sorted(providers):
        models = []
        try:
            from agent.models_dev import list_provider_models
            models = list_provider_models(provider, allow_network=True)
        except Exception:
            pass
        try:
            from providers import get_provider_profile
            profile = get_provider_profile(provider)
            for mid in list(getattr(profile, "fallback_models", []) or []):
                if mid not in models:
                    models.append(mid)
        except Exception:
            pass
        rows[provider] = sorted(dict.fromkeys(str(x) for x in models if str(x).strip()))
    return {
        "current": {"provider": current_provider, "model": current_model},
        "providers": rows,
        "owner": "Hermes",
        "note": "CMD only exposes/overrides Hermes-visible routes; Hermes remains the default routing authority.",
    }
