from __future__ import annotations
from .config import ensure_dirs
from .db_common import TERMINAL, EDITABLE
from .run_core import RunCoreMixin
from .snapshot_state import SnapshotMixin
from .plan_state import PlanStateMixin
from .learning_store import LEARNING


class Store(SnapshotMixin, RunCoreMixin, PlanStateMixin):
    def __init__(self):
        ensure_dirs()
        self.init_run_state()
        self.init_plan_state()
        self.recover_stale()

    def learning_stats(self, limit=30):
        return LEARNING.stats(limit)

    def add_learning(self, *a, **kw):
        return LEARNING.add(*a, **kw)

    def learning(self, lid):
        return LEARNING.get(lid)

    def learnings(self, limit=50, statuses=None):
        return LEARNING.list(limit, statuses)

    def update_learning(self, lid, **kw):
        return LEARNING.update(lid, **kw)

    def delete_learning(self, lid):
        return LEARNING.delete(lid)

    def relevant_learnings(self, limit=20):
        return LEARNING.list(limit, ("ACTIVE", "APPROVED"))

    def run_has_learning(self, rid):
        return LEARNING.has_run(rid)

    def ensure_learning_fallback(self, rid):
        if LEARNING.has_run(rid):
            return None
        r = self.run(rid)
        if not r:
            return None
        units = self.work_units(rid)
        failed = [u["unit_id"] for u in units if u["status"] == "FAILED"]
        retried = [u["unit_id"] for u in units if int(u.get("attempts") or 0) > 1]
        return LEARNING.add(
            "Hermes did not record a reflection for this run. CMD captured an operational observation for human/Hermes review; do not promote it to a rule without review.",
            kind="observation",
            source="cmd",
            status="CANDIDATE",
            scope="run_reflection",
            evidence=f"run={rid}; state={r.get('status')}; failed={failed}; retried={retried}",
            confidence="low",
            priority=10,
            run_id=rid,
        )


STORE = Store()
