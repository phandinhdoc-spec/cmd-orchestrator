from __future__ import annotations
from .storage import STORE


def route(task: str, task_class="general", risk="medium", mode=None):
    """Compatibility API: CMD owns role policy; Hermes exposes/executes available routes."""
    return {
        "decision_owner": "cmd_control_plane",
        "provider": "",
        "model": "",
        "reason": "CMD v1.4 routes by role policy; concrete provider/model IDs are selected from the Hermes-visible catalog.",
        "task": task,
        "task_class": task_class,
        "risk": risk,
        "mode": mode or "role_policy",
        "learning": STORE.learning_stats(10),
    }


def stats():
    return STORE.learning_stats()
