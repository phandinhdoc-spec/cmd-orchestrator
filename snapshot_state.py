from __future__ import annotations
from pathlib import Path
from .config import VERSION,CURRENT_JSON,RUNS_DIR
from .db_common import TERMINAL,now,atomic_json

class SnapshotMixin:
    def snapshot(self,rid):
        r=self.run(rid)
        if not r:return
        data={"version":VERSION,"run":r,"prompt":self.prompt(rid),"plan":self.plan_tree(rid),"latest_checkpoint":self.latest_cp(rid)}
        atomic_json(CURRENT_JSON,{"run_id":rid,"updated_at":now()}); atomic_json(RUNS_DIR/f"{rid}.json",data)
        try:
            cwd=Path.cwd()
            if (cwd/".git").exists() or (cwd/".ai").exists():
                ai=cwd/".ai"; ai.mkdir(exist_ok=True); units=self.work_units(rid)
                done=', '.join(u['unit_id'] for u in units if u['status']=='DONE') or '-'
                active=', '.join(u['unit_id'] for u in units if u['status'] not in TERMINAL) or '-'
                text=(f"# cmd-orchestrator v{VERSION} checkpoint\n\n- RUN ID: {rid}\n- STATUS: {r.get('status')}\n"
                      f"- OWNER: Hermes (CMD control plane)\n- STAGE: {r.get('current_stage') or '-'}\n"
                      f"- CURRENT: {r.get('current_task') or '-'}\n- PROGRESS: {r.get('completed_tasks',0)}/{r.get('total_tasks',0)}\n"
                      f"- DONE UNITS: {done}\n- ACTIVE/PENDING: {active}\n")
                (ai/"task_on_progress.md").write_text(text,encoding="utf-8")
        except Exception:pass
