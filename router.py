from __future__ import annotations
from .storage import STORE


def route(task: str, task_class="general", risk="medium", mode=None):
    """Compatibility API: v1.2 deliberately defers default routing to Hermes."""
    return {
        "decision_owner": "hermes",
        "provider": "",
        "model": "",
        "reason": "CMD v1.2 does not independently route work; ask Hermes to choose, then expose/override that choice.",
        "task": task,
        "task_class": task_class,
        "risk": risk,
        "mode": mode or "hermes",
        "learning": STORE.learning_stats(10),
    }


def stats():
    return STORE.learning_stats()
