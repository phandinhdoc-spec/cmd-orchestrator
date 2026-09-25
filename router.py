from __future__ import annotations
from .storage import STORE
from .config import load_settings

def locked_role(role: str, *, confirmed_user_defect=False):
    """Return the v1.5 hard-locked provider/model policy for a role."""
    roles=load_settings()["locked_roles"]
    key=str(role or "").strip().lower()
    if key not in roles:
        raise ValueError(f"unknown locked role: {role}")
    spec=dict(roles[key])
    if spec.get("confirmed_user_defect_only") and not confirmed_user_defect:
        raise PermissionError(f"{key} is incident-only and requires a user-reported defect confirmed by Hermes")
    return spec

def route(task: str, task_class="general", risk="medium", mode=None, role="manager", confirmed_user_defect=False):
    spec=locked_role(role,confirmed_user_defect=confirmed_user_defect)
    return {
        "decision_owner":"cmd_control_plane","locked":True,"role":role,
        "provider":spec.get("provider",""),"model":spec.get("model",""),
        "models":spec.get("models",[]),
        "capability_tier":spec.get("capability_tier",""),
        "reference_model":spec.get("reference_model",""),
        "selection":spec.get("selection",""),
        "fallback_provider":spec.get("fallback_provider",""),
        "fallback_model":spec.get("fallback_model",""),
        "reason":"CMD v1.5.2 role policy. Patcher is capability-locked to Terra-class, not locked to the literal Terra model.",
        "task":task,"task_class":task_class,"risk":risk,"mode":mode or "locked",
        "learning":STORE.learning_stats(10),
    }

def stats():
    return STORE.learning_stats()
