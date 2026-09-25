from __future__ import annotations
import json
from .config import load_settings
from .storage import STORE

TERMINAL_OK={"DONE","SKIPPED"}

def _planned_meta(run):
    try:
        plan=json.loads(run.get("plan_json") or "{}")
    except Exception:
        plan={}
    meta={}
    for task in plan.get("tasks") or []:
        for unit in task.get("work_units") or []:
            if isinstance(unit,dict):
                meta[str(unit.get("id") or "")]={
                    "files":list(unit.get("files") or []),
                    "symbol":str(unit.get("symbol") or ""),
                    "library_evidence":str(unit.get("library_evidence") or ""),
                }
    return meta

def ready_frontier(run_id=None, limit=None):
    """Return independent DAG-ready units for Hermes to dispatch as parallel workers."""
    run=STORE.run(run_id) if run_id else STORE.current()
    if not run:
        raise ValueError("no active run")
    rid=run["run_id"]
    units=STORE.work_units(rid)
    by_id={u["unit_id"]:u for u in units}
    meta=_planned_meta(run)
    max_parallel=max(1,int(limit or load_settings().get("max_parallel",3)))
    running=[u for u in units if u.get("status")=="RUNNING"]
    slots=max(0,max_parallel-len(running))
    if slots==0:
        return {"run_id":rid,"max_parallel":max_parallel,"running":[u["unit_id"] for u in running],"ready":[]}

    candidates=[]
    for u in units:
        if u.get("status") not in ("READY","PENDING","WAITING"):
            continue
        deps=u.get("dependencies") or []
        if all(by_id.get(d,{}).get("status") in TERMINAL_OK for d in deps):
            candidates.append(u)

    occupied=set()
    for u in running:
        occupied.update(meta.get(u["unit_id"],{}).get("files") or [])
    chosen=[]
    for u in candidates:
        files=set(meta.get(u["unit_id"],{}).get("files") or [])
        if files and files & occupied:
            continue
        chosen.append({**u,**meta.get(u["unit_id"],{})})
        occupied.update(files)
        if len(chosen)>=slots:
            break
    return {
        "run_id":rid,"max_parallel":max_parallel,
        "running":[u["unit_id"] for u in running],
        "ready":chosen,
        "instruction":"Dispatch each ready item to a separate worker concurrently. Workers must stay inside their write scope, must not recursively orchestrate, and must report verification back to Hermes.",
    }
